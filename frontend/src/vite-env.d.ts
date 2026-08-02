/// <reference types="vite/client" />

interface Window {
  Telegram?: {
    WebApp?: {
      ready: () => void;
      expand: () => void;
      colorScheme?: "light" | "dark";
      initData?: string;
      initDataUnsafe?: {
        user?: {
          language_code?: string;
        };
      };
      setHeaderColor?: (color: string) => void;
      setBackgroundColor?: (color: string) => void;
      HapticFeedback?: {
        notificationOccurred?: (type: "error" | "success" | "warning") => void;
      };
      BackButton?: {
        show: () => void;
        hide: () => void;
        onClick: (callback: () => void) => void;
        offClick: (callback: () => void) => void;
      };
    };
  };
}
