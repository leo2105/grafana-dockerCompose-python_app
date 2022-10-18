# grafana-dockerCompose-python_app

1. Install docker and docker-compose

2. `docker-compose up --build -d` (build the containers)

3. `docker-compose ps` (get the names of the containers)

3. `docker exec -it <app_container_name> bash` (access to app container)

4. run `python3.8 run.py` (run the application to send info to prometheus)

5. go to browser, `localhost:29800`, prometheus UI (check time series sent)

6. go to browser, `localhost:3000`, grafana UI (check the dashboard)