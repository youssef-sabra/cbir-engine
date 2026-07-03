# Build-free static dashboard served by nginx. No npm toolchain — the SPA is
# plain HTML/CSS/JS (build context is this directory).
FROM nginx:1.27-alpine
COPY index.html styles.css app.js /usr/share/nginx/html/
EXPOSE 80
