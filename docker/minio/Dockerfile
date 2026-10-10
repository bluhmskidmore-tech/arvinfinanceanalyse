# MinIO Community is source-only. Fetch only this pinned official source tree;
# the build context contains no application source, environment files or data.
ARG MINIO_COMMIT=7aac2a2c5b7c882e68c1ce017d8256be2feea27f
FROM golang:1.27.1-alpine3.24 AS build
ARG MINIO_COMMIT
ENV CGO_ENABLED=0 GOTOOLCHAIN=local
RUN apk add --no-cache git
WORKDIR /src/minio
RUN git init && \
    git remote add origin https://github.com/minio/minio.git && \
    git fetch --depth 1 origin "${MINIO_COMMIT}" && \
    git checkout --detach FETCH_HEAD && \
    test "$(git rev-parse HEAD)" = "${MINIO_COMMIT}" && \
    build_flags="$(go run buildscripts/gen-ldflags.go)" && \
    go build -mod=readonly -trimpath \
      -ldflags="${build_flags}" -o /out/minio . && \
    /out/minio --version

FROM alpine:3.24.2
ARG MINIO_COMMIT
LABEL org.opencontainers.image.source="https://github.com/minio/minio" \
      org.opencontainers.image.revision="${MINIO_COMMIT}" \
      org.opencontainers.image.licenses="AGPL-3.0-or-later"
RUN apk add --no-cache ca-certificates
COPY --from=build /out/minio /usr/local/bin/minio
COPY --from=build /src/minio/dockerscripts/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
COPY --from=build /src/minio/LICENSE /licenses/minio/LICENSE
EXPOSE 9000 9001
VOLUME ["/data"]
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["minio"]
