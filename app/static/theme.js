// Paleta da marca: vermelho #c81e25, carvão #1f1f1f, prata #e4e4e4.
// Carregar DEPOIS do script do Tailwind CDN. As classes "indigo/violet/fuchsia" do projeto passam a
// ser o vermelho da marca e "slate" vira cinza neutro (sem o tom azulado).
(function () {
  const brand = {
    50: '#fdf2f2', 100: '#fde3e4', 200: '#fbcbcd', 300: '#f6a3a6', 400: '#ee6b70',
    500: '#e03a40', 600: '#c81e25', 700: '#a8171d', 800: '#8b171c', 900: '#73181c', 950: '#3f080a',
  };
  const neutral = {
    50: '#fafafa', 100: '#f5f5f5', 200: '#e5e5e5', 300: '#d4d4d4', 400: '#a3a3a3',
    500: '#737373', 600: '#525252', 700: '#404040', 800: '#262626', 900: '#171717', 950: '#0a0a0a',
  };
  window.tailwind = window.tailwind || {};
  tailwind.config = { theme: { extend: { colors: { indigo: brand, violet: brand, fuchsia: brand, brand, slate: neutral } } } };
})();
