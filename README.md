# grafana-dockerCompose-python_app

## Usage

1. Install docker and docker-compose

2. `docker-compose up --build -d` (build the containers)

3. `docker-compose ps` (get the names of the containers)

4. `docker exec -it <app_container_name> bash` (access to app container)

5. run `python3.8 run.py` (run the application to send info to prometheus)

6. go to browser, `localhost:29800`, prometheus UI (check time series sent)

    6.1 Select `KPI_1` and execute.

7. go to browser, `localhost:3000`, grafana UI (check the dashboard)

    7.1 User: `admin`
    
    7.2 Pass: `admin`