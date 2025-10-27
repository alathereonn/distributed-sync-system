from locust import HttpUser, task, between

class LockUser(HttpUser):
    wait_time = between(0.01,0.1)
    @task
    def lock_cycle(self):
        self.client.post("/lock/acquire", json={"key":"k1","mode":"S","client_id":"c1"})
        self.client.post("/lock/release", json={"key":"k1","client_id":"c1"})
