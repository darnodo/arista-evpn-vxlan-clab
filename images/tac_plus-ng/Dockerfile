# tac_plus-ng (TACACS+ server) built from upstream source, no official image exists.
# Pinned commit for reproducible builds, bump TAC_PLUS_NG_REF to upgrade.
FROM alpine:3 AS build
ARG TAC_PLUS_NG_REF=70bf938b542d63bca00d50be0874a38a290319e0
RUN apk add --no-cache build-base git perl pcre2-dev openssl-dev c-ares-dev linux-headers bash
RUN git clone https://github.com/MarcJHuber/event-driven-servers.git /src \
 && git -C /src checkout "$TAC_PLUS_NG_REF"
WORKDIR /src
RUN ./configure --prefix=/usr/local tac_plus-ng && make && make install

FROM alpine:3
RUN apk add --no-cache pcre2 openssl c-ares libgcc
COPY --from=build /usr/local /usr/local
ENTRYPOINT ["/usr/local/sbin/tac_plus-ng", "-f"]
CMD ["/etc/tac_plus-ng.cfg"]
