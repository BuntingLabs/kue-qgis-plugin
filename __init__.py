# Copyright Bunting Labs, Inc. 2024

def classFactory(interface):
    from .kue import KuePlugin
    return KuePlugin(interface)
