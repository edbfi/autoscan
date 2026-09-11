# syntax=docker/dockerfile:1
# check=skip=InvalidDefaultArgInFrom
ARG UPSTREAM_IMAGE
ARG UPSTREAM_DIGEST_ARM64
ARG BUILDER_DIGEST_ARM64
FROM golang@${BUILDER_DIGEST_ARM64} AS builder
RUN apk add --no-cache gcc libc-dev
ARG VERSION
ARG SOURCE_REF
ARG SOURCE_SHA256
ENV GOTOOLCHAIN=local
RUN wget -O /tmp/source.tar.gz "https://codeload.github.com/Cloudbox/autoscan/tar.gz/${SOURCE_REF}" && \
    echo "${SOURCE_SHA256}  /tmp/source.tar.gz" | sha256sum -c - && \
    mkdir /autoscan && tar xzf /tmp/source.tar.gz -C /autoscan --strip-components=1
WORKDIR /autoscan
RUN go mod download && go mod verify && \
    go build -mod=readonly -trimpath -ldflags "-X main.Version=${VERSION} -X main.GitCommit=${SOURCE_REF}" -o autoscan ./cmd/autoscan && \
    go version -m autoscan > build-info.txt && \
    sha256sum autoscan > binary-sha256.txt
FROM ${UPSTREAM_IMAGE}@${UPSTREAM_DIGEST_ARM64}
EXPOSE 3030
ARG IMAGE_STATS
ENV IMAGE_STATS=${IMAGE_STATS} WEBUI_PORTS="3030/tcp"
COPY --from=builder /autoscan/autoscan ${APP_DIR}/autoscan
COPY --from=builder /autoscan/build-info.txt /autoscan/binary-sha256.txt /app/build-evidence/
COPY root/ /
RUN find /etc/s6-overlay/s6-rc.d -name "run*" -execdir chmod +x {} +
