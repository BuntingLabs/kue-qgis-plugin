# Copyright Bunting Labs, Inc. 2024

import os
from osgeo import ogr, osr, gdal
from time import time
import numpy as np

import csv
from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsPointXY, QgsProject, QgsTask, QgsApplication



def levenshtein_distance(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if not s2:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]

def humanize_atime(atime: int) -> str:
    delta = int(time()) - atime
    
    minutes = delta // 60
    hours = minutes // 60
    days = hours // 24
    months = days // 30
    years = days // 365
    
    if years > 0:
        return f"{years} years ago"
    if months > 0:
        return f"{months} months ago"
    if days > 0:
        return f"{days} days ago"
    if hours > 0:
        return f"{hours} hours ago"
    return f"{minutes} minutes ago"

def get_trigrams(text: str) -> set:
    """Get overlapping trigrams from text."""
    text = text.lower()
    return {text[i:i+3] for i in range(len(text)-2)} if len(text) > 2 else {text}

class IndexingTask(QgsTask):
    def __init__(self, dir_path, description='Indexing files for Kue /find'):
        super().__init__(description, QgsTask.CanCancel)
        self.dir_path = dir_path
        self.filename_trigrams = {}
        self.files = []
        self.exception = None
        self.processed_files = 0

    def run(self):
        try:
            files_to_index = []
            # Build index once
            for root, _, files in os.walk(self.dir_path):
                if self.isCanceled():
                    return False
                if root.startswith('.'):
                    continue

                for file in files:
                    if file.endswith(('.shp', '.tif')) and not file.startswith('.'):
                        files_to_index.append(os.path.join(root, file))

            target_srs = osr.SpatialReference()
            target_srs.ImportFromEPSG(4326)
            # Cache transformations

            for full_path in files_to_index:
                if self.isCanceled():
                    return False

                self.processed_files += 1
                self.setProgress(int(100 * self.processed_files / len(files_to_index)))

                stats = os.stat(full_path)

                if file.endswith('.shp'):
                    ds = ogr.Open(full_path)
                    if ds is None:
                        continue
                    layer = ds.GetLayer(0)
                    geom_type = ogr.GeometryTypeToName(layer.GetGeomType())
                    file_type = 'vector'
                    layer_names = [layer.GetName()]
                    
                    # Get source SRS
                    source_srs = layer.GetSpatialRef()

                    # Get extent and transform if needed
                    bbox = layer.GetExtent() # Returns (minx,maxx,miny,maxy)
                    if source_srs and source_srs.GetAuthorityCode(None) != '4326':
                        transform = osr.CoordinateTransformation(source_srs, target_srs)
                        # Ensure traditional lon/lat axis order
                        target_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

                        # Convert bbox corners preserving lon/lat order
                        point_sw = ogr.CreateGeometryFromWkt(f'POINT ({bbox[0]} {bbox[2]})') # minx,miny
                        point_ne = ogr.CreateGeometryFromWkt(f'POINT ({bbox[1]} {bbox[3]})') # maxx,maxy
                        point_sw.Transform(transform)
                        point_ne.Transform(transform)
                        # Order as minx,miny,maxx,maxy (min_lon,min_lat,max_lon,max_lat)
                        bbox = (
                            point_sw.GetX(),
                            point_sw.GetY(),
                            point_ne.GetX(),
                            point_ne.GetY()
                        )

                    ds = None
                else:
                    file_type = 'raster'
                    geom_type = None
                    bbox = None
                    layer_names = []

                    ds = gdal.Open(full_path)
                    if ds:
                        geotransform = ds.GetGeoTransform()
                        if geotransform:
                            width = ds.RasterXSize
                            height = ds.RasterYSize

                            # Calculate bounding box coordinates
                            minx = geotransform[0]
                            maxy = geotransform[3]
                            maxx = minx + width * geotransform[1]
                            miny = maxy + height * geotransform[5]
                            bbox = (minx, miny, maxx, maxy) # Already in min_lon,min_lat,max_lon,max_lat order
                            # Transform to EPSG:4326 if needed
                            source_crs = QgsCoordinateReferenceSystem(ds.GetProjection())
                            if source_crs.isValid() and source_crs.authid() != 'EPSG:4326':
                                target_crs = QgsCoordinateReferenceSystem('EPSG:4326')
                                transform = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance())
                                transform.setAllowFallbackTransforms(True)
                                
                                try:
                                    # Check for inf values
                                    if any(abs(x) == float('inf') for x in bbox):
                                        bbox = None
                                    else:
                                        # Transform corners preserving lon/lat order
                                        point_sw = transform.transform(QgsPointXY(bbox[0], bbox[1])) # min_lon,min_lat
                                        point_ne = transform.transform(QgsPointXY(bbox[2], bbox[3])) # max_lon,max_lat
                                        bbox = (point_sw.x(), point_sw.y(), point_ne.x(), point_ne.y())
                                except:
                                    bbox = None
                    ds = None

                self.files.append({
                    'path': full_path,
                    'last_accessed': int(stats.st_atime),
                    'last_modified': int(stats.st_mtime),
                    'type': file_type,
                    'geometry_type': geom_type,
                    'layer_names': layer_names,
                    'bbox': bbox
                })
                # Precompute trigrams for filename
                filename = os.path.basename(full_path)
                self.filename_trigrams[full_path] = get_trigrams(filename)

            return True

        except Exception as e:
            self.exception = e
            return False

    def finished(self, result):
        if result and not self.isCanceled():
            self.setProgress(100)

class KueFind:
    def __init__(self):
        self.files = []
        self.bbox_finder = BBoxFinder(os.path.join(os.path.dirname(__file__), 'regions_and_countries.csv'))
        self.filename_trigrams = {}
        self.index_task = None
        self.index_task_trash = []  # Keep reference to prevent garbage collection
        
    def index(self, dir_path: str):
        # Create and start the indexing task
        self.index_task = IndexingTask(dir_path)
        
        def task_completed(exception=None, result=None):
            if exception is None:
                self.files = self.index_task.files
                self.filename_trigrams = self.index_task.filename_trigrams
            self.index_task_trash.append(self.index_task)  # Prevent garbage collection
            self.index_task = None
            
        self.index_task.taskCompleted.connect(task_completed)
        self.index_task.taskTerminated.connect(task_completed)
        
        QgsApplication.taskManager().addTask(self.index_task)

    def search(self, query: str, n: int = 12):
        # Start indexing if not already started
        if not self.filename_trigrams and self.index_task is None:
            self.index(os.path.expanduser("~"))
            return []

        query_words = query.lower().split()

        def score_filename(file_info):
            query_trigrams = get_trigrams(' '.join(query_words))
            file_trigrams = self.filename_trigrams[file_info['path']]
            
            intersection = len(query_trigrams & file_trigrams)
            union = len(query_trigrams | file_trigrams)
            return -intersection/union if union > 0 else 0

        results = sorted(self.files, key=score_filename)[:n]
        return [(
            f['path'],
            humanize_atime(f['last_accessed']),
            f['type'],
            f['geometry_type'],
            self.bbox_finder.find_containing_bbox(f['bbox']) if f['bbox'] else ''
        ) for f in results]

class BBoxFinder:
    def __init__(self, bbox_file):
        self.names = []

        with open(bbox_file) as f:
            num_lines = sum(1 for line in f) - 1  # Subtract 1 for header

        self.bboxes = np.empty((num_lines+1, 4), dtype=np.float32)
        # Special boxes
        self.names.append('Null Island')
        self.bboxes[0] = [-3.0, -3.0, 3.0, 3.0]

        with open(bbox_file) as f:
            reader = csv.reader(f)
            next(reader) # Skip header
            for i, row in enumerate(reader):
                name, minx, miny, maxx, maxy = row
                self.names.append(name)
                self.bboxes[i+1] = [float(minx), float(miny), float(maxx), float(maxy)]

        # Pre-compute areas
        self.areas = (self.bboxes[:,2] - self.bboxes[:,0]) * (self.bboxes[:,3] - self.bboxes[:,1])

    def find_containing_bbox(self, query_bbox):
        # Unpack query bbox
        qminx, qminy, qmaxx, qmaxy = query_bbox

        # Find all bboxes that contain the query
        contains = (self.bboxes[:,0] <= qminx) & (self.bboxes[:,1] <= qminy) & \
                  (self.bboxes[:,2] >= qmaxx) & (self.bboxes[:,3] >= qmaxy)

        if not np.any(contains):
            return "World"

        # Get the smallest containing bbox
        containing_idx = contains.nonzero()[0]
        min_area_idx = containing_idx[np.argmin(self.areas[containing_idx])]

        return self.names[min_area_idx]



