import requests


class PrometheusClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def get_metric(self, query: str) -> float:
        url = f"{self.base_url}/api/v1/query"
        response = requests.get(url, params={"query": query})
        response.raise_for_status()
        data = response.json()
        if data.get("status") != "success" or not data["data"]["result"]:
            return 0.0
        return float(data["data"]["result"][0]["value"][1])

    def get_avg_cpu_usage(self, label: str) -> float:
        query = 'sum(rate(container_cpu_usage_seconds_total{job="cadvisor"}[1m]) * 0.01)'
        return self.get_metric(query)

    def get_container_count(self, label: str) -> int:
        query = (
            'count('
            'container_memory_usage_bytes'
            '{job="cadvisor",container_label_autoscale_service="' + label + '"}'
            ')'
        )
        return int(self.get_metric(query))
