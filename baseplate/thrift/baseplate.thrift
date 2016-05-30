namespace py baseplate.thrift

/** The base for any baseplate-based service.

Your service should inherit from this one so that common tools can interact
with any expected interfaces.

*/
service BaseplateService {
    /** Return whether or not the service is healthy.

    The healthchecker (baseplate.server.healthcheck) expects this endpoint to
    exist so it can determine your service's health.

    This should return True if the service is healthy. If the service is
    unhealthy, it can return False or raise an exception.

    */
    bool is_healthy(),
}

struct ClientId {
  1: string name
}

struct RequestContext {
  1: binary key,
  2: binary value
}

struct Delegation {
  1: string src
  2: string dst
}

struct RequestHeader {
  1: i64 trace_id,
  2: i64 span_id,
  3: optional i64 parent_span_id,
  5: optional bool sampled,
  6: optional ClientId client_id,
  7: optional i64 flags,
  8: list<RequestContext> contexts,

  // Support for destination (partially resolved names) and delegation tables.
  9: optional string dest,
  10: optional list<Delegation> delegations,
}

struct ConnectionOptions {
}

struct UpgradeReply {
}
