# Requirements

    - Docker Desktop

# Installing

Open a powershell terminal

Execute the next command
```shell
docker compose up --build -d
```

# Running

In Docker desktop confirm that you have de `ninemanga-crawler - ninemanga.app` already running

Execute the next command:
```shell
docker exec -it ninemanga.app python cli.py
```