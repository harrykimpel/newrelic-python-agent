# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: opentelemetry/proto/resource/v1/resource.proto
"""Generated protocol buffer code."""
from google.protobuf.internal import builder as _builder
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from opentelemetry.proto.common.v1 import common_pb2 as opentelemetry_dot_proto_dot_common_dot_v1_dot_common__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n.opentelemetry/proto/resource/v1/resource.proto\x12\x1fopentelemetry.proto.resource.v1\x1a*opentelemetry/proto/common/v1/common.proto\"i\n\x08Resource\x12;\n\nattributes\x18\x01 \x03(\x0b\x32\'.opentelemetry.proto.common.v1.KeyValue\x12 \n\x18\x64ropped_attributes_count\x18\x02 \x01(\rB\x83\x01\n\"io.opentelemetry.proto.resource.v1B\rResourceProtoP\x01Z*go.opentelemetry.io/proto/otlp/resource/v1\xaa\x02\x1fOpenTelemetry.Proto.Resource.V1b\x06proto3')

_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, globals())
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'opentelemetry.proto.resource.v1.resource_pb2', globals())
if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  DESCRIPTOR._serialized_options = b'\n\"io.opentelemetry.proto.resource.v1B\rResourceProtoP\001Z*go.opentelemetry.io/proto/otlp/resource/v1\252\002\037OpenTelemetry.Proto.Resource.V1'
  _RESOURCE._serialized_start=127
  _RESOURCE._serialized_end=232
# @@protoc_insertion_point(module_scope)
