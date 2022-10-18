FROM node:12.20.1 as node

WORKDIR /app/grafana-cvx-display-panel
COPY plugins/grafana-cvx-display-panel /app/grafana-cvx-display-panel

RUN npm install
RUN npm run-script build

FROM grafana/grafana:7.3.6

USER root

COPY --from=node /app/grafana-cvx-display-panel /var/lib/grafana-plugins/grafana-cvx-display-panel
