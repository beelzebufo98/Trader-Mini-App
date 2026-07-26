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
        title: "Signal settings",
        subtitle: "Fill in the required parameters to request a signal.",
        market: "Market",
        language: "Language",
        pair: "Trading pair",
        pairPlaceholder: "Choose pair",
        pairSearch: "Search pair",
        noPairs: "No pairs found",
        model: "Model",
        modelPlaceholder: "Choose model",
        expiration: "Expiration",
        expirationPlaceholder: "Choose time",
        getSignal: "Get signal",
        generating: "Generating signal...",
        readyTitle: "Everything selected",
        readyText: "Signal generation animation can start.",
        errorTitle: "Not everything selected",
        errorText: "Fix the highlighted fields and try again."
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
        title: "Настройки сигнала",
        subtitle: "Заполните обязательные параметры, чтобы запросить сигнал.",
        market: "Рынок",
        language: "Язык",
        pair: "Торговая пара",
        pairPlaceholder: "Выберите пару",
        pairSearch: "Поиск пары",
        noPairs: "Пары не найдены",
        model: "Модель",
        modelPlaceholder: "Выберите модель",
        expiration: "Экспирация",
        expirationPlaceholder: "Выберите время",
        getSignal: "Получить сигнал",
        generating: "Генерация сигнала...",
        readyTitle: "Все выбрано",
        readyText: "Можно запускать анимацию генерации сигнала.",
        errorTitle: "Не все выбрано",
        errorText: "Показываем ошибки и не запускаем сигнал."
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
        title: "Ajustes de señal",
        subtitle: "Completa los parámetros requeridos para solicitar una señal.",
        market: "Mercado",
        language: "Idioma",
        pair: "Par de trading",
        pairPlaceholder: "Elige par",
        pairSearch: "Buscar par",
        noPairs: "No se encontraron pares",
        model: "Modelo",
        modelPlaceholder: "Elige modelo",
        expiration: "Expiración",
        expirationPlaceholder: "Elige tiempo",
        getSignal: "Obtener señal",
        generating: "Generando señal...",
        readyTitle: "Todo seleccionado",
        readyText: "La animación de generación puede comenzar.",
        errorTitle: "Faltan parámetros",
        errorText: "Corrige los campos marcados y vuelve a intentarlo."
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
        title: "Configurações do sinal",
        subtitle: "Preencha os parâmetros obrigatórios para solicitar um sinal.",
        market: "Mercado",
        language: "Idioma",
        pair: "Par de trading",
        pairPlaceholder: "Escolha o par",
        pairSearch: "Buscar par",
        noPairs: "Nenhum par encontrado",
        model: "Modelo",
        modelPlaceholder: "Escolha o modelo",
        expiration: "Expiração",
        expirationPlaceholder: "Escolha o tempo",
        getSignal: "Obter sinal",
        generating: "Gerando sinal...",
        readyTitle: "Tudo selecionado",
        readyText: "A animação de geração pode começar.",
        errorTitle: "Faltam parâmetros",
        errorText: "Corrija os campos destacados e tente novamente."
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
        title: "Sinyal ayarları",
        subtitle: "Sinyal istemek için gerekli parametreleri doldurun.",
        market: "Piyasa",
        language: "Dil",
        pair: "İşlem çifti",
        pairPlaceholder: "Çift seçin",
        pairSearch: "Çift ara",
        noPairs: "Çift bulunamadı",
        model: "Model",
        modelPlaceholder: "Model seçin",
        expiration: "Vade",
        expirationPlaceholder: "Süre seçin",
        getSignal: "Sinyal al",
        generating: "Sinyal oluşturuluyor...",
        readyTitle: "Her şey seçildi",
        readyText: "Sinyal oluşturma animasyonu başlayabilir.",
        errorTitle: "Eksik seçim var",
        errorText: "İşaretli alanları düzeltip tekrar deneyin."
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
        title: "إعدادات الإشارة",
        subtitle: "املأ الحقول المطلوبة لطلب الإشارة.",
        market: "السوق",
        language: "اللغة",
        pair: "زوج التداول",
        pairPlaceholder: "اختر الزوج",
        pairSearch: "ابحث عن زوج",
        noPairs: "لم يتم العثور على أزواج",
        model: "النموذج",
        modelPlaceholder: "اختر النموذج",
        expiration: "الانتهاء",
        expirationPlaceholder: "اختر الوقت",
        getSignal: "احصل على إشارة",
        generating: "جار إنشاء الإشارة...",
        readyTitle: "تم اختيار كل شيء",
        readyText: "يمكن بدء حركة إنشاء الإشارة.",
        errorTitle: "ليست كل الحقول مكتملة",
        errorText: "صحح الحقول المحددة وحاول مرة أخرى."
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
