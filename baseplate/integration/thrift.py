"""Thrift integration for Baseplate.

This module provides an implementation of :py:class:`TProcessor` which
integrates Baseplate's facilities into the Thrift request lifecycle.

An abbreviated example of it in use::

    def make_processor(app_config):
        baseplate = Baseplate()
        handler = MyHandler()
        return TBaseplateProcessor(logger, baseplate, handler)

TODO:

- prereq: centralize root span creation stuff
- lots of code cleanup
  - baseplate.integration.thrift.load_thriftfile -> baseplate.thrift_pool?
  - move the two load_thrift("baseplate.thrift") calls to one place?
  - baseplate.integration.thrift.TBaseplateProcessor
  - baseplate.thrift_pool._make_protocol
  - baseplate.context.thrift.*
  - baseplate.server.healthcheck.*
  - baseplate.thrift (and maybe it should move out of thrift/?)
- fix the tests, get some integration testing?
- make the client work
- test against real finagle
- test against theaderprotocol r2 clients for upgrade path
- evaluate thriftpy again
- travis


"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import posixpath

import pkg_resources
import thriftpy
from thriftpy.thrift import (
    TApplicationException,
    TException,
    TMessageType,
    TType,
)

from ..core import TraceInfo


def load_thrift(package_name, resource_name):
    thriftfile_path = pkg_resources.resource_filename(package_name, resource_name)

    package_components = [package_name]
    subdirectories, thriftfile_name = posixpath.split(resource_name)
    package_components.extend(filter(None, subdirectories.split(posixpath.sep)))
    module_basename, extension = posixpath.splitext(thriftfile_name)
    assert extension == ".thrift"
    package_components.append(module_basename + "_thrift")
    module_path = ".".join(package_components)

    baseplate_thriftfile = pkg_resources.resource_filename(
        "baseplate", "thrift/baseplate.thrift")
    include_dir = os.path.dirname(baseplate_thriftfile).encode()
    include_dirs = [include_dir]

    # TODO: cleaner way to deal with encoding here?
    return thriftpy.load(thriftfile_path.encode(), module_path.encode(), include_dirs)


baseplate_thrift = load_thrift("baseplate", "thrift/baseplate.thrift")


class RequestContext(object):
    pass


class TBaseplateProcessor(object):
    def __init__(self, logger, baseplate, service, handler):
        self.logger = logger
        self.baseplate = baseplate
        self.service = service
        self.handler = handler
        self.is_upgraded = False

    def process(self, iprot, oprot):
        if self.is_upgraded:
            header = baseplate_thrift.RequestHeader()
            header.read(iprot)
        else:
            header = None

        name, message_type, sequence_id = iprot.read_message_begin()
        assert message_type in (TMessageType.CALL, TMessageType.ONEWAY)
        if name in self.special_method_readers:
            args = baseplate_thrift.ConnectionOptions()
            args.read(iprot)
            handler = self.special_method_readers[name]
        elif name in self.service.thrift_services:
            args_cls = getattr(self.service, "{}_args".format(name))
            args = args_cls()
            args.read(iprot)
            handler = self._handle_method_call
        else:
            iprot.skip(TType.STRUCT)
            handler = self._handle_not_found
        iprot.read_message_end()

        try:
            result = handler(name, header, args)
        except Exception as exc:
            oprot.write_message_begin(name, TMessageType.EXCEPTION, sequence_id)
            if not isinstance(exc, TException):
                exc = TApplicationException(type=TApplicationException.INTERNAL_ERROR,
                                            message=str(exc))
            exc.write(oprot)
            oprot.write_message_end()
            oprot.trans.flush()
        else:
            if not result.oneway:
                oprot.write_message_begin(name, TMessageType.REPLY, sequence_id)
                result.write(oprot)
                oprot.write_message_end()
                oprot.trans.flush()

    def _handle_upgrade(self, name, header, args):
        self.is_upgraded = True
        return baseplate_thrift.UpgradeReply()

    def _handle_not_found(self, name, header, args):
        raise TApplicationException(TApplicationException.UNKNOWN_METHOD)

    def _handle_method_call(self, name, header, args):
        result_cls = getattr(self.service, "{}_result".format(name))
        result = result_cls()

        arg_indexes = sorted(args.thrift_spec.keys())
        arg_names = [args.thrift_spec[i][1] for i in arg_indexes]
        ordered_args = [args.__dict__[arg_name] for arg_name in arg_names]

        if header:
            trace_info = TraceInfo(
                header.trace_id, header.span_id, header.parent_span_id)
        else:
            trace_info = None

        context = RequestContext()
        root_span = self.baseplate.make_root_span(
            context=context,
            name=name,
            trace_info=trace_info,
        )

        handler_method = getattr(self.handler, name)
        try:
            self.logger.debug("Handling: %r", name)
            with root_span:
                result.success = handler_method(context, *ordered_args)
        except Exception as exc:
            for index, spec in result.thrift_spec.items():
                if spec[1] == "success":
                    continue

                _, exc_name, exc_cls, _ = spec
                if isinstance(exc, exc_cls):
                    setattr(result, exc_name, exc)
                    break
            else:
                raise

        return result

    special_method_readers = {
        "__baseplate_trace_v1__": _handle_upgrade,
    }
