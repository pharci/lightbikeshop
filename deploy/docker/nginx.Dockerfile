FROM nginx:1.27.5-alpine AS build

ARG NGINX_VERSION=1.27.5

RUN apk add --no-cache \
    git \
    build-base \
    pcre2-dev \
    zlib-dev \
    openssl-dev \
    wget \
    cmake

WORKDIR /tmp

# ngx_brotli + Brotli
RUN git clone --depth=1 https://github.com/google/ngx_brotli.git \
    && cd ngx_brotli \
    && git submodule update --init --recursive \
    && cd deps/brotli \
    && mkdir -p out \
    && cd out \
    && cmake -DCMAKE_BUILD_TYPE=Release .. \
    && make -j"$(nproc)"

# Исходники nginx и сборка динамических модулей
RUN wget "http://nginx.org/download/nginx-${NGINX_VERSION}.tar.gz" \
    && tar xzf "nginx-${NGINX_VERSION}.tar.gz" \
    && cd "nginx-${NGINX_VERSION}" \
    && ./configure \
        --with-compat \
        --add-dynamic-module=../ngx_brotli \
    && make modules


FROM nginx:1.27.5-alpine

COPY --from=build \
    /tmp/nginx-1.27.5/objs/ngx_http_brotli_filter_module.so \
    /etc/nginx/modules/

COPY --from=build \
    /tmp/nginx-1.27.5/objs/ngx_http_brotli_static_module.so \
    /etc/nginx/modules/

RUN mkdir -p \
    /var/www/static \
    /var/www/media \
    /var/www/certbot/.well-known/acme-challenge

COPY deploy/nginx/nginx.conf /etc/nginx/nginx.conf
COPY deploy/nginx/nginx.dev.conf /etc/nginx/nginx.dev.conf
COPY deploy/nginx/nginx.prod.conf /etc/nginx/nginx.prod.conf

EXPOSE 80 443

CMD ["nginx", "-g", "daemon off;"]