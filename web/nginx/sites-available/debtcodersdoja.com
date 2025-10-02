server {
    listen 80;
    listen [::]:80;
    server_name debtcodersdoja.com www.debtcodersdoja.com;

    root /var/www/debtcodersdoja.com;
    index index.html;

    access_log /var/log/nginx/debtcodersdoja.access.log;
    error_log  /var/log/nginx/debtcodersdoja.error.log;

    location / {
        try_files $uri $uri/ =404;
    }
}
