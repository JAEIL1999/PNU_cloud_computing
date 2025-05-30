class RoundRobinBalancer:
    def __init__(self, servers):
        self.servers = servers
        self.index = 0

    def get_next_server(self):
        if not self.servers:
            raise Exception("No backend servers available.")
        server = self.servers[self.index]
        self.index = (self.index + 1) % len(self.servers)
        return server
