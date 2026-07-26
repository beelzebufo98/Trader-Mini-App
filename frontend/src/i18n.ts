import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import type { AppLanguage } from "./types";

const resources = {
  en: {
    translation: {
      intro: {
        eyebrow: "Trading Bot",
        cardTitle: "Paradox trading system",
        subtitle: "Professional signals for a stable result",
        marketTitle: "Choose market",
        languageTitle: "Language",
        continue: "Continue",
        forex: "Forex market",
        otc: "OTC market"
      },
      dashboard: {
        back: "Back",
        title: "Signal workspace",
        subtitle: "{{market}} mode is selected. Broker connection and live signals will be added later.",
        market: "Market",
        language: "Language",
        status: "Interface prototype",
        emptyTitle: "Signals are not connected yet",
        emptyText: "At this stage the Mini App only stores user choices and prepares the interface flow."
      },
      languages: {
        auto: "Auto",
        ru: "Русский",
        en: "English",
        es: "Español",
        pt: "Português",
        tr: "Türkçe",
        ar: "العربية"
      }
    }
  },
  ru: {
    translation: {
      intro: {
        eyebrow: "Trading Bot",
        cardTitle: "Торговая система Paradox",
        subtitle: "Профессиональные сигналы для стабильного результата",
        marketTitle: "Выберите рынок",
        languageTitle: "Язык",
        continue: "Продолжить",
        forex: "Forex рынок",
        otc: "OTC рынок"
      },
      dashboard: {
        back: "Назад",
        title: "Рабочая область сигналов",
        subtitle: "Выбран режим {{market}}. Подключение брокеров и реальные сигналы будут добавлены позже.",
        market: "Рынок",
        language: "Язык",
        status: "Прототип интерфейса",
        emptyTitle: "Сигналы пока не подключены",
        emptyText: "На этом этапе Mini App сохраняет выбор пользователя и готовит сценарий интерфейса."
      },
      languages: {
        auto: "Авто",
        ru: "Русский",
        en: "English",
        es: "Español",
        pt: "Português",
        tr: "Türkçe",
        ar: "العربية"
      }
    }
  },
  es: {
    translation: {
      intro: {
        eyebrow: "Trading Bot",
        cardTitle: "Sistema de trading Paradox",
        subtitle: "Señales profesionales para un resultado estable",
        marketTitle: "Elige mercado",
        languageTitle: "Idioma",
        continue: "Continuar",
        forex: "Mercado Forex",
        otc: "Mercado OTC"
      },
      dashboard: {
        back: "Atrás",
        title: "Panel de señales",
        subtitle: "Modo {{market}} seleccionado. Brokers y señales reales se agregarán después.",
        market: "Mercado",
        language: "Idioma",
        status: "Prototipo de interfaz",
        emptyTitle: "Las señales aún no están conectadas",
        emptyText: "En esta etapa Mini App guarda la selección del usuario y prepara el flujo."
      },
      languages: {
        auto: "Auto",
        ru: "Русский",
        en: "English",
        es: "Español",
        pt: "Português",
        tr: "Türkçe",
        ar: "العربية"
      }
    }
  },
  pt: {
    translation: {
      intro: {
        eyebrow: "Trading Bot",
        cardTitle: "Sistema de trading Paradox",
        subtitle: "Sinais profissionais para um resultado estável",
        marketTitle: "Escolha o mercado",
        languageTitle: "Idioma",
        continue: "Continuar",
        forex: "Mercado Forex",
        otc: "Mercado OTC"
      },
      dashboard: {
        back: "Voltar",
        title: "Área de sinais",
        subtitle: "Modo {{market}} selecionado. Brokers e sinais reais serão adicionados depois.",
        market: "Mercado",
        language: "Idioma",
        status: "Protótipo da interface",
        emptyTitle: "Os sinais ainda não estão conectados",
        emptyText: "Nesta etapa, o Mini App salva a escolha do usuário e prepara o fluxo."
      },
      languages: {
        auto: "Auto",
        ru: "Русский",
        en: "English",
        es: "Español",
        pt: "Português",
        tr: "Türkçe",
        ar: "العربية"
      }
    }
  },
  tr: {
    translation: {
      intro: {
        eyebrow: "Trading Bot",
        cardTitle: "Paradox trading sistemi",
        subtitle: "Kararlı sonuç için profesyonel sinyaller",
        marketTitle: "Piyasa seçin",
        languageTitle: "Dil",
        continue: "Devam",
        forex: "Forex piyasası",
        otc: "OTC piyasası"
      },
      dashboard: {
        back: "Geri",
        title: "Sinyal alanı",
        subtitle: "{{market}} modu seçildi. Broker bağlantısı ve canlı sinyaller daha sonra eklenecek.",
        market: "Piyasa",
        language: "Dil",
        status: "Arayüz prototipi",
        emptyTitle: "Sinyaller henüz bağlı değil",
        emptyText: "Bu aşamada Mini App kullanıcı seçimlerini kaydeder ve arayüz akışını hazırlar."
      },
      languages: {
        auto: "Auto",
        ru: "Русский",
        en: "English",
        es: "Español",
        pt: "Português",
        tr: "Türkçe",
        ar: "العربية"
      }
    }
  },
  ar: {
    translation: {
      intro: {
        eyebrow: "Trading Bot",
        cardTitle: "نظام تداول Paradox",
        subtitle: "إشارات احترافية لنتيجة مستقرة",
        marketTitle: "اختر السوق",
        languageTitle: "اللغة",
        continue: "متابعة",
        forex: "سوق Forex",
        otc: "سوق OTC"
      },
      dashboard: {
        back: "رجوع",
        title: "مساحة الإشارات",
        subtitle: "تم اختيار وضع {{market}}. سيتم إضافة الوسطاء والإشارات الحية لاحقا.",
        market: "السوق",
        language: "اللغة",
        status: "نموذج واجهة",
        emptyTitle: "الإشارات غير متصلة بعد",
        emptyText: "في هذه المرحلة يحفظ Mini App اختيارات المستخدم ويجهز مسار الواجهة."
      },
      languages: {
        auto: "Auto",
        ru: "Русский",
        en: "English",
        es: "Español",
        pt: "Português",
        tr: "Türkçe",
        ar: "العربية"
      }
    }
  }
};

export function detectAppLanguage(): Exclude<AppLanguage, "auto"> {
  const telegramLanguage = window.Telegram?.WebApp?.initDataUnsafe?.user?.language_code;
  const browserLanguage = navigator.language;
  const language = (telegramLanguage || browserLanguage || "en").toLowerCase();

  if (language.startsWith("ru")) return "ru";
  if (language.startsWith("es")) return "es";
  if (language.startsWith("pt")) return "pt";
  if (language.startsWith("tr")) return "tr";
  if (language.startsWith("ar")) return "ar";
  return "en";
}

export function resolveLanguage(language: AppLanguage) {
  return language === "auto" ? detectAppLanguage() : language;
}

i18n.use(initReactI18next).init({
  resources,
  lng: detectAppLanguage(),
  fallbackLng: "en",
  interpolation: {
    escapeValue: false
  }
});

export { i18n };
