# Copyright 2024 Bunting Labs, Inc.

from enum import Enum


class KueResponseStatus(str, Enum):
    OK = "OK"
    AMBIGUOUS = "AMBIGUOUS"
    USER_CANCELLED = "USER_CANCELLED"
    ERROR = "ERROR"
    POLLING = "POLLING"


def status_to_color(status: KueResponseStatus) -> str:
    if status == KueResponseStatus.OK:
        return "green"
    elif status == KueResponseStatus.AMBIGUOUS:
        return "orange"
    elif status == KueResponseStatus.USER_CANCELLED:
        return "red"
    elif status == KueResponseStatus.ERROR:
        return "red"
    elif status == KueResponseStatus.POLLING:
        return "orange"


KUE_INTRODUCTION_MESSAGES = {
    "en": [
        "I'm Kue, an AI assistant that can read and edit QGIS projects.",
        "How can I help you today?",
    ],
    "pt": [
        "Sou o Kue, um assistente de IA que pode ler e editar projetos QGIS.",
        "Como posso te ajudar hoje?",
    ],
    "fr": [
        "Je suis Kue, un assistant IA capable de lire et d'éditer des projets QGIS.",
        "Comment puis-je vous aider aujourd'hui ?",
    ],
    "de": [
        "Ich bin Kue, ein KI-Assistent, der QGIS-Projekte lesen und bearbeiten kann.",
        "Wie kann ich Ihnen heute helfen?",
    ],
    "es": [
        "Soy Kue, un asistente de IA que puede leer y editar proyectos QGIS.",
        "¿Cómo puedo ayudarte hoy?",
    ],
    "it": [
        "Sono Kue, un assistente IA che può leggere e modificare progetti QGIS.",
        "Come posso aiutarti oggi?",
    ],
    "hi": [
        "मैं क्यू, एक एआई सहायक हूं जो QGIS प्रोजेक्ट्स को पढ़ और संपादित कर सकता है।",
        "आज मैं आपकी कैसे मदद कर सकता हूँ?",
    ],
    "bn": [
        "আমি কু, একটি AI সহকারী যা QGIS প্রকল্পগুলি পড়তে এবং সম্পাদনা করতে পারে।",
        "আজ আমি আপনাকে কীভাবে সাহায্য করতে পারি?",
    ],
    "he": [
        "אני קיו, עוזר AI שיכול לקרוא ולערוך פרויקטים של QGIS.",
        "?כיצד אוכל לעזור לך היום",
    ],
    "lv": [
        "Es esmu Kue, AI asistents, kas var lasīt un rediģēt QGIS projektus.",
        "Kā es varu jums šodien palīdzēt?",
    ],
    "pl": [
        "Jestem Kue, asystentem AI, który może czytać i edytować projekty QGIS.",
        "Jak mogę ci dziś pomóc?",
    ],
    "nl": [
        "Ik ben Kue, een AI-assistent die QGIS-projecten kan lezen en bewerken.",
        "Hoe kan ik je vandaag helpen?",
    ],
    "sv": [
        "Jag är Kue, en AI-assistent som kan läsa och redigera QGIS-projekt.",
        "Hur kan jag hjälpa dig idag?",
    ],
    "da": [
        "Jeg er Kue, en AI-assistent, der kan læse og redigere QGIS-projekter.",
        "Hvordan kan jeg hjælpe dig i dag?",
    ],
    "cs": [
        "Jsem Kue, AI asistent, který umí číst a upravovat projekty QGIS.",
        "Jak vám mohu dnes pomoci?",
    ],
    "ro": [
        "Sunt Kue, un asistent AI care poate citi și edita proiecte QGIS.",
        "Cum vă pot ajuta astăzi?",
    ],
    "tr": [
        "Ben Kue, QGIS projelerini okuyabilen ve düzenleyebilen bir AI asistanıyım.",
        "Bugün size nasıl yardımcı olabilirim?",
    ],
}

KUE_ASK_KUE = {
    "en": "Ask Kue...",
    "pt": "Perguntar ao Kue...",
    "fr": "Demander à Kue...",
    "de": "Kue fragen...",
    "es": "Pregunta a Kue...",
    "it": "Chiedi a Kue...",
    "hi": "क्यू से पूछें...",
    "bn": "কু-কে জিজ্ঞাসা করুন...",
    "he": "...שאל את קיו",
    "lv": "Jautāt Kue...",
    "pl": "Zapytaj Kue...",
    "nl": "Vraag Kue...",
    "sv": "Fråga Kue...",
    "da": "Spørg Kue...",
    "cs": "Zeptejte se Kue...",
    "ro": "Întreabă Kue...",
    "tr": "Kue'ye sor...",
}

KUE_FIND_FILTER_EXPLANATION = {
    "en": "Filter for files in map canvas",
    "pt": "Filtrar arquivos no canvas do mapa",
    "fr": "Filtrer les fichiers dans le canevas de carte",
    "de": "Dateien in der Kartenansicht filtern",
    "es": "Filtrar archivos en el lienzo del mapa",
    "it": "Filtra i file nel canvas della mappa",
    "hi": "मानचित्र कैनवास में फ़ाइलें फ़िल्टर करें",
    "bn": "ম্যাপ ক্যানভাসে ফাইল ফিল্টার করুন",
    "he": "סנן קבצים בקנבס המפה",
    "lv": "Filtrēt failus kartes kanvā",
    "pl": "Filtruj pliki na kanwie mapy",
    "nl": "Bestanden filteren in kaartcanvas",
    "sv": "Filtrera filer i kartfönstret",
    "da": "Filtrer filer i kortlærredet",
    "cs": "Filtrovat soubory v mapovém plátně",
    "ro": "Filtrează fișierele în canvas-ul hărții",
    "tr": "Harita tuvalinde dosyaları filtrele",
}

KUE_CLEAR_CHAT = {
    "en": "Clear chat",
    "pt": "Limpar conversa",
    "fr": "Effacer la conversation",
    "de": "Chat löschen",
    "es": "Borrar chat",
    "it": "Cancella chat",
    "hi": "चैट साफ़ करें",
    "bn": "চ্যাট মুছুন",
    "he": "נקה צ'אט",
    "lv": "Notīrīt tērzēšanu",
    "pl": "Wyczyść czat",
    "nl": "Chat wissen",
    "sv": "Rensa chatten",
    "da": "Ryd chat",
    "cs": "Vymazat chat",
    "ro": "Șterge conversația",
    "tr": "Sohbeti temizle",
}
