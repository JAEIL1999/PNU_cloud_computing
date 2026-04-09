import logging

import requests


class LoadBalancerNotifier:
    def __init__(self, load_balancer_url: str):
        self.load_balancer_url = load_balancer_url

    def notify_refresh(self) -> None:
        try:
            refresh_url = f"{self.load_balancer_url}/refresh-servers"
            response = requests.post(refresh_url, timeout=3)

            if response.status_code == 200:
                logging.info("Load balancer server refresh triggered")
            else:
                logging.warning("Load balancer refresh failed: %s", response.status_code)
        except requests.exceptions.ConnectionError:
            logging.warning("Could not connect to load balancer")
        except requests.exceptions.Timeout:
            logging.warning("Load balancer request timed out")
        except Exception as error:
            logging.error("Error notifying load balancer: %s", error)
