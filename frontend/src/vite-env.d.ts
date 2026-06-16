/// <reference types="vite/client" />

interface Window {
  Telegram?: {
    WebApp?: {
      ready: () => void;
      expand: () => void;
      colorScheme?: "light" | "dark";
      setHeaderColor?: (color: string) => void;
      setBackgroundColor?: (color: string) => void;
    };
  };
}
