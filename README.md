# Bot de ofertas Black Friday 🛍️

Lee los feeds RSS de webs de chollos (Chollometro, Promodescuentos…), que recogen ofertas
de Amazon, MediaMarkt, PcComponentes, Mercado Libre, Liverpool, etc. Filtra por tus palabras
clave, precio y descuento, y te avisa por Telegram. Sin dependencias: solo Python 3.

## 1. Crear el bot de Telegram
1. En Telegram, habla con **@BotFather** → `/newbot` → copia el **token**.
2. Escribe cualquier mensaje a tu bot nuevo.
3. Abre `https://api.telegram.org/bot<TOKEN>/getUpdates` y copia `"chat":{"id": ...}`.

## 2. Configurar
Edita `config.json`: pon tus búsquedas (`palabras`, `excluir`, `precio_max`, `descuento_min`,
`tiendas`) y deja solo los feeds de tu país. El token puedes ponerlo como variable de entorno:

    export TELEGRAM_TOKEN="123:ABC..."
    export TELEGRAM_CHAT_ID="123456789"

## 3. Ejecutar
    python3 bot.py            # revisa cada 10 minutos sin parar
    python3 bot.py --una-vez  # una sola pasada (útil con cron)

Sin Telegram configurado, las ofertas se muestran en la consola.
`vistos.json` guarda las ofertas ya avisadas para no repetirlas. Pon
`"ignorar_existentes_al_arrancar": true` si no quieres recibir de golpe las del primer arranque.
