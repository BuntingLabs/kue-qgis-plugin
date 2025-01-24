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
    "hr": [
        "Ja sam Kue, AI asistent koji može čitati i uređivati QGIS projekte.",
        "Kako vam mogu pomoći danas?",
    ],
    "uk": [
        "Я Кю, AI-асистент, який може читати та редагувати проекти QGIS.",
        "Як я можу вам допомогти сьогодні?",
    ],
    "ru": [
        "Я Кю, AI-ассистент, который может читать и редактировать проекты QGIS.",
        "Как я могу помочь вам сегодня?",
    ],
    "zh": [
        "我是Kue，一个可以读取和编辑QGIS项目的AI助手。",
        "今天我能帮您什么？",
    ],
    "ja": [
        "私はKueです。QGISプロジェクトを読み取り、編集できるAIアシスタントです。",
        "今日はどのようにお手伝いできますか？",
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
    "hr": "Pitaj Kue...",
    "uk": "Запитайте Kue...",
    "ru": "Спросите Kue...",
    "zh": "询问Kue...",
    "ja": "Kueに聞く...",
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
    "hr": "Filtriraj datoteke u platnu karte",
    "uk": "Фільтрувати файли на полотні карти",
    "ru": "Фильтровать файлы на холсте карты",
    "zh": "在地图画布中过滤文件",
    "ja": "マップキャンバスでファイルをフィルタリング",
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
    "hr": "Očisti chat",
    "uk": "Очистити чат",
    "ru": "Очистить чат",
    "zh": "清除聊天",
    "ja": "チャットをクリア",
}

KUE_DESCRIPTION = {
    "en": "Kue is an embedded AI assistant inside QGIS. It can read and edit your project, using cloud AI services to do so (LLMs).",
    "pt": "Kue é um assistente de IA embutido no QGIS. Ele pode ler e editar seu projeto, usando serviços de IA em nuvem para isso (LLMs).",
    "fr": "Kue est un assistant IA intégré dans QGIS. Il peut lire et éditer votre projet en utilisant des services d'IA en nuage (LLMs).",
    "de": "Kue ist ein eingebetteter KI-Assistent in QGIS. Er kann Ihr Projekt lesen und bearbeiten, indem er Cloud-KI-Dienste nutzt (LLMs).",
    "es": "Kue es un asistente de IA integrado en QGIS. Puede leer y editar su proyecto utilizando servicios de IA en la nube (LLMs).",
    "it": "Kue è un assistente AI integrato in QGIS. Può leggere e modificare il tuo progetto utilizzando servizi di IA cloud (LLMs).",
    "hi": "Kue QGIS के अंदर एक एम्बेडेड AI सहायक है। यह आपके प्रोजेक्ट को पढ़ और संपादित कर सकता है, इसके लिए क्लाउड AI सेवाओं का उपयोग करता है (LLMs)।",
    "bn": "Kue হল QGIS এর ভিতরে এম্বেড করা একটি AI সহকারী। এটি আপনার প্রকল্প পড়তে এবং সম্পাদনা করতে পারে, এটি করার জন্য ক্লাউড AI পরিষেবাগুলি ব্যবহার করে (LLMs)।",
    "he": "Kue הוא עוזר AI משובץ בתוך QGIS. הוא יכול לקרוא ולערוך את הפרויקט שלך, תוך שימוש בשירותי AI בענן לשם כך (LLMs).",
    "lv": "Kue ir iegults AI asistents QGIS iekšienē. Tas var lasīt un rediģēt jūsu projektu, izmantojot mākoņa AI pakalpojumus (LLMs).",
    "pl": "Kue to wbudowany asystent AI w QGIS. Może czytać i edytować Twój projekt, korzystając z usług AI w chmurze (LLMs).",
    "nl": "Kue is een ingebouwde AI-assistent in QGIS. Het kan uw project lezen en bewerken met behulp van cloud-AI-diensten (LLMs).",
    "sv": "Kue är en inbäddad AI-assistent i QGIS. Den kan läsa och redigera ditt projekt med hjälp av moln-AI-tjänster (LLMs).",
    "da": "Kue er en indlejret AI-assistent i QGIS. Den kan læse og redigere dit projekt ved hjælp af cloud-AI-tjenester (LLMs).",
    "cs": "Kue je vestavěný AI asistent v QGIS. Může číst a upravovat váš projekt pomocí cloudových AI služeb (LLMs).",
    "ro": "Kue este un asistent AI integrat în QGIS. Poate citi și edita proiectul dvs. folosind servicii AI în cloud (LLMs).",
    "tr": "Kue, QGIS içinde gömülü bir AI asistanıdır. Projenizi okuyabilir ve düzenleyebilir, bunu yapmak için bulut AI hizmetlerini kullanır (LLMs).",
    "hr": "Kue je ugrađeni AI asistent unutar QGIS-a. Može čitati i uređivati vaš projekt koristeći usluge AI u oblaku (LLMs).",
    "uk": "Kue — це вбудований AI-асистент у QGIS. Він може читати та редагувати ваш проект, використовуючи хмарні AI-сервіси (LLMs).",
    "ru": "Kue — это встроенный AI-ассистент в QGIS. Он может читать и редактировать ваш проект, используя облачные AI-сервисы (LLMs).",
    "zh": "Kue 是 QGIS 中的嵌入式 AI 助手。它可以读取和编辑您的项目，使用云 AI 服务来实现 (LLMs)。",
    "ja": "Kue は QGIS 内の埋め込み型 AI アシスタントです。クラウド AI サービスを使用してプロジェクトを読み取り、編集できます (LLMs)。",
}

KUE_SUBSCRIPTION = {
    "en": "Using Kue requires a subscription of $19/month (first month free). This allows us to build useful AI tools.",
    "pt": "Usar o Kue requer uma assinatura de $19/mês (primeiro mês grátis). Isso nos permite construir ferramentas de IA úteis.",
    "fr": "L'utilisation de Kue nécessite un abonnement de 19 $/mois (premier mois gratuit). Cela nous permet de créer des outils d'IA utiles.",
    "de": "Die Nutzung von Kue erfordert ein Abonnement von 19 $/Monat (erster Monat kostenlos). Dies ermöglicht es uns, nützliche KI-Tools zu entwickeln.",
    "es": "Usar Kue requiere una suscripción de $19/mes (primer mes gratis). Esto nos permite construir herramientas de IA útiles.",
    "it": "L'utilizzo di Kue richiede un abbonamento di $19/mese (primo mese gratuito). Questo ci consente di creare strumenti di IA utili.",
    "hi": "Kue का उपयोग करने के लिए $19/माह की सदस्यता की आवश्यकता होती है (पहला महीना मुफ्त)। यह हमें उपयोगी AI उपकरण बनाने की अनुमति देता है।",
    "bn": "Kue ব্যবহার করতে $19/মাস সাবস্ক্রিপশন প্রয়োজন (প্রথম মাস বিনামূল্যে)। এটি আমাদেরকে দরকারী AI সরঞ্জাম তৈরি করতে সক্ষম করে।",
    "he": "שימוש ב-Kue דורש מנוי של $19 לחודש (החודש הראשון חינם). זה מאפשר לנו לבנות כלים שימושיים של AI.",
    "lv": "Kue lietošanai nepieciešams abonements par $19/mēnesī (pirmais mēnesis bez maksas). Tas ļauj mums izveidot noderīgus AI rīkus.",
    "pl": "Korzystanie z Kue wymaga subskrypcji w wysokości 19 $/miesiąc (pierwszy miesiąc za darmo). To pozwala nam tworzyć przydatne narzędzia AI.",
    "nl": "Het gebruik van Kue vereist een abonnement van $19/maand (eerste maand gratis). Dit stelt ons in staat om nuttige AI-tools te bouwen.",
    "sv": "Att använda Kue kräver en prenumeration på $19/månad (första månaden gratis). Detta gör att vi kan bygga användbara AI-verktyg.",
    "da": "Brug af Kue kræver et abonnement på $19/måned (første måned gratis). Dette giver os mulighed for at bygge nyttige AI-værktøjer.",
    "cs": "Používání Kue vyžaduje předplatné 19 $/měsíc (první měsíc zdarma). To nám umožňuje vytvářet užitečné nástroje AI.",
    "ro": "Utilizarea Kue necesită un abonament de 19 $/lună (prima lună gratuită). Acest lucru ne permite să construim instrumente AI utile.",
    "tr": "Kue kullanmak, $19/ay abonelik gerektirir (ilk ay ücretsiz). Bu, faydalı AI araçları geliştirmemizi sağlar.",
    "hr": "Korištenje Kue zahtijeva pretplatu od 19 $/mjesec (prvi mjesec besplatno). To nam omogućuje izradu korisnih AI alata.",
    "uk": "Використання Kue вимагає підписки $19/місяць (перший місяць безкоштовно). Це дозволяє нам створювати корисні AI інструменти.",
    "ru": "Использование Kue требует подписки $19/месяц (первый месяц бесплатно). Это позволяет нам создавать полезные AI инструменты.",
    "zh": "使用 Kue 需要每月 $19 的订阅（第一个月免费）。这使我们能够构建有用的 AI 工具。",
    "ja": "Kue の使用には月額 $19 のサブスクリプションが必要です（初月無料）。これにより、便利な AI ツールを構築できます。",
}

KUE_START_BUTTON = {
    "en": "Get Started",
    "pt": "Começar",
    "fr": "Commencer",
    "de": "Loslegen",
    "es": "Empezar",
    "it": "Iniziare",
    "hi": "शुरू करें",
    "bn": "শুরু করুন",
    "he": "להתחיל",
    "lv": "Sākt darbu",
    "pl": "Rozpocznij",
    "nl": "Aan de slag",
    "sv": "Kom igång",
    "da": "Kom i gang",
    "cs": "Začít",
    "ro": "Începe",
    "tr": "Başla",
    "hr": "Započni",
    "uk": "Розпочати",
    "ru": "Начать",
    "zh": "开始使用",
    "ja": "始める",
}

KUE_LOGIN_BUTTON = {
    "en": "Use Existing Account",
    "pt": "Usar Conta Existente",
    "fr": "Utiliser un Compte Existant",
    "de": "Bestehendes Konto Verwenden",
    "es": "Usar Cuenta Existente",
    "it": "Usa Account Esistente",
    "hi": "मौजूदा खाता उपयोग करें",
    "bn": "বিদ্যমান অ্যাকাউন্ট ব্যবহার করুন",
    "he": "השתמש בחשבון קיים",
    "lv": "Izmantot Esošo Kontu",
    "pl": "Użyj Istniejącego Konta",
    "nl": "Gebruik Bestaand Account",
    "sv": "Använd Befintligt Konto",
    "da": "Brug Eksisterende Konto",
    "cs": "Použít Existující Účet",
    "ro": "Folosește Cont Existent",
    "tr": "Mevcut Hesabı Kullan",
    "hr": "Koristi Postojeći Račun",
    "uk": "Використати Існуючий Акаунт",
    "ru": "Использовать Существующий Аккаунт",
    "zh": "使用现有帐号",
    "ja": "既存のアカウントを使用",
}
