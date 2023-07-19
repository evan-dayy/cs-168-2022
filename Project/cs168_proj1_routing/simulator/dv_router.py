"""
Your awesome Distance Vector router for CS 168

Based on skeleton code by:
  MurphyMc, zhangwen0411, lab352
"""
from collections import defaultdict
import sim.api as api
from cs168.dv import RoutePacket, \
                     Table, TableEntry, \
                     DVRouterBase, Ports, \
                     FOREVER, INFINITY

class DVRouter(DVRouterBase):

    # A route should time out after this interval
    ROUTE_TTL = 15

    # Dead entries should time out after this interval
    GARBAGE_TTL = 10

    # -----------------------------------------------
    # At most one of these should ever be on at once
    SPLIT_HORIZON = False
    POISON_REVERSE = False
    # -----------------------------------------------
    
    # Determines if you send poison for expired routes
    POISON_EXPIRED = False

    # Determines if you send updates when a link comes up
    SEND_ON_LINK_UP = False

    # Determines if you send poison when a link goes down
    POISON_ON_LINK_DOWN = False
    
    HISTORY = {}

    def __init__(self):
        """
        Called when the instance is initialized.
        DO NOT remove any existing code from this method.
        However, feel free to add to it for memory purposes in the final stage!
        """
        assert not (self.SPLIT_HORIZON and self.POISON_REVERSE), \
                    "Split horizon and poison reverse can't both be on"
        
        self.start_timer()  # Starts signaling the timer at correct rate.

        # Contains all current ports and their latencies.
        # See the write-up for documentation.
        self.ports = Ports()
        
        # This is the table that contains all current routes
        self.table = Table()
        self.table.owner = self


    def add_static_route(self, host, port):
        """
        Adds a static route to this router's table.

        Called automatically by the framework whenever a host is connected
        to this router.

        :param host: the host.
        :param port: the port that the host is attached to.
        :returns: nothing.
        """
        # `port` should have been added to `peer_tables` by `handle_link_up`
        # when the link came up.
        assert port in self.ports.get_all_ports(), "Link should be up, but is not."

        # TODO: fill this in!
        rte = TableEntry(host, 
                         port,
                         latency= self.ports.link_to_lat[port], # default link latency to that port
                         expire_time=FOREVER)
        self.table[host] = rte
        
        
    def handle_data_packet(self, packet, in_port):
        """
        Called when a data packet arrives at this router.

        You may want to forward the packet, drop the packet, etc. here.

        :param packet: the packet that arrived.
        :param in_port: the port from which the packet arrived.
        :return: nothing.
        """
        # TODO: fill this in!
        if packet.dst not in self.table or self.table[packet.dst].latency >= INFINITY:
            return # package is dropped
        self.send(packet, port=self.table[packet.dst].port, flood=False)
        
        

    def send_routes(self, force=False, single_port=None):
        """
        Send route advertisements for all routes in the table.

        :param force: if True, advertises ALL routes in the table;
                      otherwise, advertises only those routes that have
                      changed since the last advertisement.
               single_port: if not None, sends updates only to that port; to
                            be used in conjunction with handle_link_up.
        :return: nothing.
        """
        # TODO: fill this in!
        
        # in conjunction with handle_link_up.
        if self.SEND_ON_LINK_UP and single_port is not None:
            for dst in self.table:
                curr_latency = self.table[dst].latency
                advertise_pkt = RoutePacket(destination=dst, 
                                            latency=curr_latency)
                self.send(advertise_pkt, port=single_port, flood=False)
                self.HISTORY[(dst, port)] = curr_latency
            return
        
        for dst in self.table:
            curr_latency = self.table[dst].latency
            for port in self.ports.get_all_ports():
                x = curr_latency
                # Module: Split Horizon
                # --------------------------------------------------------
                if (self.SPLIT_HORIZON and port == self.table[dst].port):
                    continue
                # --------------------------------------------------------
                
                advertise_pkt = RoutePacket(destination=dst, 
                                            latency=x)
                # Module: Poison Reverse
                # --------------------------------------------------------
                if (self.POISON_REVERSE and port == self.table[dst].port):
                    x = INFINITY
                    advertise_pkt = RoutePacket(destination=dst, 
                                            latency=x)
                # --------------------------------------------------------
                if force:
                    self.send(advertise_pkt, port=port, flood=False)
                    self.HISTORY[(dst, port)] = x
                else:
                    if (dst, port) not in self.HISTORY or self.HISTORY[(dst, port)] != x:
                        self.send(advertise_pkt, port=port, flood=False)
                        self.HISTORY[(dst, port)] = x

    def expire_routes(self):
        """
        Clears out expired routes from table.
        accordingly.
        """
        # TODO: fill this in!
        removed = []
        for dst in self.table:
            if self.table[dst].expire_time <= api.current_time():
                removed.append(dst)
        for dst in removed:
            # Module: Poison Expired
            # --------------------------------------------------------
            if self.POISON_EXPIRED:
                self.table[dst] = TableEntry(
                    dst,
                    self.table[dst].port,
                    INFINITY,
                    api.current_time() + self.ROUTE_TTL)
                continue
            
            # --------------------------------------------------------
            self.s_log("Removing route to %s" % dst) # logging the message
            del self.table[dst]
            

    def handle_route_advertisement(self, route_dst, route_latency, port):
        """
        Called when the router receives a route advertisement from a neighbor.

        :param route_dst: the destination of the advertised route.
        :param route_latency: latency from the neighbor to the destination.
        :param port: the port that the advertisement arrived on.
        :return: nothing.
        """
        # TODO: fill this in!
        if route_dst not in self.table:
            self.table[route_dst] = TableEntry(
                        route_dst, 
                        port,
                        latency= route_latency + self.ports.link_to_lat[port],
                        expire_time=api.current_time() + self.ROUTE_TTL)
            self.send_routes(force=False)
            return
        
        curr_route = self.table[route_dst]
        # Counting to Infinity (Poison Reversed)
        # --------------------------------------------------------
        if curr_route.port == port and route_latency >= INFINITY:
            self.table[route_dst] = TableEntry(
                        route_dst, 
                        port,
                        latency=INFINITY,
                        expire_time=api.current_time() + self.ROUTE_TTL)
            self.send_routes(force=False)
            return
        # --------------------------------------------------------
        if curr_route.port == port or route_latency + self.ports.link_to_lat[port] < curr_route.latency:
            self.table[route_dst] = TableEntry(
                        route_dst, 
                        port,
                        latency=route_latency + self.ports.link_to_lat[port],
                        expire_time=api.current_time() + self.ROUTE_TTL)
            self.send_routes(force=False)
            return
        

    def handle_link_up(self, port, latency):
        """
        Called by the framework when a link attached to this router goes up.

        :param port: the port that the link is attached to.
        :param latency: the link latency.
        :returns: nothing.
        """
        self.ports.add_port(port, latency)
        # TODO: fill in the rest!
        self.send_routes(force=True, single_port=port)


    def handle_link_down(self, port):
        """
        Called by the framework when a link attached to this router does down.

        :param port: the port number used by the link.
        :returns: nothing.
        """
        self.ports.remove_port(port)
        removed = []
        for dst in self.table:
            if self.table[dst].port == port:
                removed.append(dst)
        for dst in removed:
            # Module: Poison Expired
            # --------------------------------------------------------
            if self.POISON_ON_LINK_DOWN:
                self.table[dst] = TableEntry(
                    dst,
                    self.table[dst].port,
                    INFINITY,
                    api.current_time() + self.ROUTE_TTL)
                self.send_routes(force=False)
                continue
            # --------------------------------------------------------
            self.s_log("Removing route to %s" % dst) # logging the message
            del self.table[dst]

        # TODO: fill this in!

    # Feel free to add any helper methods!
