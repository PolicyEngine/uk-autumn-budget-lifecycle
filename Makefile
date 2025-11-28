.PHONY: run clean docker docker-down dev

# Static chart
run:
	uv run python build_chart.py
	open chart_output.html

# Docker
docker:
	docker compose up --build -d
	@echo "Frontend: http://localhost:3000"
	@echo "API: http://localhost:8000"
	open http://localhost:3000

docker-down:
	docker compose down

# Local dev (no docker)
dev:
	cd backend && uv run uvicorn main:app --reload --port 8000 &
	@sleep 2
	open frontend/index.html

clean:
	rm -f lifetime_results.csv lifetime_impacts.png chart_output.html
