# Copyright 2010 New Relic, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import google.generativeai as genai
from testing_support.fixtures import (
    override_llm_token_callback_settings,
    reset_core_stats_engine,
    validate_attributes,
)
from testing_support.ml_testing_utils import (  # noqa: F401
    add_token_count_to_events,
    disabled_ai_monitoring_record_content_settings,
    disabled_ai_monitoring_settings,
    disabled_ai_monitoring_streaming_settings,
    events_sans_content,
    events_sans_llm_metadata,
    events_with_context_attrs,
    llm_token_count_callback,
    set_trace_info,
)
from testing_support.validators.validate_custom_event import validate_custom_event_count
from testing_support.validators.validate_custom_events import validate_custom_events
from testing_support.validators.validate_transaction_metrics import (
    validate_transaction_metrics,
)

from newrelic.api.background_task import background_task
from newrelic.api.llm_custom_attributes import WithLlmCustomAttributes
from newrelic.api.transaction import add_custom_attribute

_test_gemini_chat_completion_messages = (
    "You are a scientist.",
    "What is 212 degrees Fahrenheit converted to Celsius?",
)

chat_completion_recorded_events = [
    (
        {"type": "LlmChatCompletionSummary"},
        {
            "id": None,  # UUID that varies with each run
            "llm.conversation_id": "my-awesome-id",
            "llm.foo": "bar",
            "span_id": None,
            "trace_id": "trace-id",
            "request_id": "49dbbffbd3c3f4612aa48def69059ccd",
            "duration": None,  # Response time varies each test run
            "request.model": "gemini-1.5-flash",
            "response.model": "gemini-1.5-flash",
            "response.organization": "new-relic-nkmd8b",
            "request.temperature": 0.7,
            "request.max_tokens": 100,
            "response.choices.finish_reason": "stop",
            "response.headers.llmVersion": "2020-10-01",
            "response.headers.ratelimitLimitRequests": 200,
            "response.headers.ratelimitLimitTokens": 40000,
            "response.headers.ratelimitResetTokens": "90ms",
            "response.headers.ratelimitResetRequests": "7m12s",
            "response.headers.ratelimitRemainingTokens": 39940,
            "response.headers.ratelimitRemainingRequests": 199,
            "vendor": "gemini",
            "ingest_source": "Python",
            "response.number_of_messages": 3,
        },
    ),
    (
        {"type": "LlmChatCompletionMessage"},
        {
            "id": "chatcmpl-87sb95K4EF2nuJRcTs43Tm9ntTemv-0",
            "llm.conversation_id": "my-awesome-id",
            "llm.foo": "bar",
            "request_id": "49dbbffbd3c3f4612aa48def69059ccd",
            "span_id": None,
            "trace_id": "trace-id",
            "content": "You are a scientist.",
            "role": "system",
            "completion_id": None,
            "sequence": 0,
            "response.model": "gemini-1.5-flash",
            "vendor": "gemini",
            "ingest_source": "Python",
        },
    ),
    (
        {"type": "LlmChatCompletionMessage"},
        {
            "id": "chatcmpl-87sb95K4EF2nuJRcTs43Tm9ntTemv-1",
            "llm.conversation_id": "my-awesome-id",
            "llm.foo": "bar",
            "request_id": "49dbbffbd3c3f4612aa48def69059ccd",
            "span_id": None,
            "trace_id": "trace-id",
            "content": "What is 212 degrees Fahrenheit converted to Celsius?",
            "role": "user",
            "completion_id": None,
            "sequence": 1,
            "response.model": "gemini-1.5-flash",
            "vendor": "gemini",
            "ingest_source": "Python",
        },
    ),
    (
        {"type": "LlmChatCompletionMessage"},
        {
            "id": "chatcmpl-87sb95K4EF2nuJRcTs43Tm9ntTemv-2",
            "llm.conversation_id": "my-awesome-id",
            "llm.foo": "bar",
            "request_id": "49dbbffbd3c3f4612aa48def69059ccd",
            "span_id": None,
            "trace_id": "trace-id",
            "content": "212 degrees Fahrenheit is equal to 100 degrees Celsius.",
            "role": "assistant",
            "completion_id": None,
            "sequence": 2,
            "response.model": "gemini-1.5-flash",
            "vendor": "gemini",
            "is_response": True,
            "ingest_source": "Python",
        },
    ),
]


@reset_core_stats_engine()
#@validate_custom_events(events_with_context_attrs(chat_completion_recorded_events))
# One summary event, one system message, one user message, and one response message from the assistant
@validate_custom_event_count(count=3)
@validate_transaction_metrics(
    name="test_chat_completion:test_gemini_chat_completion_sync_with_llm_metadata",
    custom_metrics=[
        (f"Supportability/Python/ML/Gemini/{genai.__version__}", 1),
    ],
    background_task=True,
)
@validate_attributes("agent", ["llm"])
@background_task()
def test_gemini_chat_completion_sync_with_llm_metadata(set_trace_info, sync_gemini_client):
    set_trace_info()
    add_custom_attribute("llm.conversation_id", "my-awesome-id")
    add_custom_attribute("llm.foo", "bar")
    add_custom_attribute("non_llm_attr", "python-agent")
    with WithLlmCustomAttributes({"context": "attr"}):
        sync_gemini_client.generate_content(
            _test_gemini_chat_completion_messages,
            generation_config=genai.types.GenerationConfig(
                temperature=0.7
            )
        )


@reset_core_stats_engine()
@disabled_ai_monitoring_record_content_settings
#@validate_custom_events(events_sans_content(chat_completion_recorded_events))
# One summary event, one system message, one user message, and one response message from the assistant
@validate_custom_event_count(count=3)
@validate_transaction_metrics(
    name="test_chat_completion:test_gemini_chat_completion_sync_no_content",
    custom_metrics=[
        (f"Supportability/Python/ML/Gemini/{genai.__version__}", 1),
    ],
    background_task=True,
)
@validate_attributes("agent", ["llm"])
@background_task()
def test_gemini_chat_completion_sync_no_content(set_trace_info, sync_gemini_client):
    set_trace_info()
    add_custom_attribute("llm.conversation_id", "my-awesome-id")
    add_custom_attribute("llm.foo", "bar")

    sync_gemini_client.generate_content(
        _test_gemini_chat_completion_messages,
        generation_config=genai.types.GenerationConfig(
            temperature=0.7
        )
    )

@reset_core_stats_engine()
@override_llm_token_callback_settings(llm_token_count_callback)
#@validate_custom_events(add_token_count_to_events(chat_completion_recorded_events))
# One summary event, one system message, one user message, and one response message from the assistant
@validate_custom_event_count(count=3)
@validate_transaction_metrics(
    name="test_chat_completion:test_gemini_chat_completion_sync_with_token_count",
    custom_metrics=[
        (f"Supportability/Python/ML/Gemini/{genai.__version__}", 1),
    ],
    background_task=True,
)
@validate_attributes("agent", ["llm"])
@background_task()
def test_gemini_chat_completion_sync_with_token_count(set_trace_info, sync_gemini_client):
    set_trace_info()
    add_custom_attribute("llm.conversation_id", "my-awesome-id")
    add_custom_attribute("llm.foo", "bar")

    #genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    #model = genai.GenerativeModel("gemini-1.5-flash")
    sync_gemini_client.generate_content(
        _test_gemini_chat_completion_messages,
        generation_config=genai.types.GenerationConfig(
            temperature=0.7
        )
    )


@reset_core_stats_engine()
#@validate_custom_events(events_sans_llm_metadata(chat_completion_recorded_events))
# One summary event, one system message, one user message, and one response message from the assistant
@validate_custom_event_count(count=3)
@validate_transaction_metrics(
    "test_chat_completion:test_gemini_chat_completion_sync_no_llm_metadata",
    scoped_metrics=[("Llm/completion/Gemini/generate_content", 1)],
    rollup_metrics=[("Llm/completion/Gemini/generate_content", 1)],
    background_task=True,
)
@background_task()
def test_gemini_chat_completion_sync_no_llm_metadata(set_trace_info, sync_gemini_client):
    set_trace_info()

    sync_gemini_client.generate_content(
        _test_gemini_chat_completion_messages,
        generation_config=genai.types.GenerationConfig(
            temperature=0.7
        )
    )


@reset_core_stats_engine()
@validate_custom_event_count(count=0)
def test_gemini_chat_completion_sync_outside_txn(sync_gemini_client):
    sync_gemini_client.generate_content(
        _test_gemini_chat_completion_messages,
        generation_config=genai.types.GenerationConfig(
            temperature=0.7
        )
    )


@disabled_ai_monitoring_settings
@reset_core_stats_engine()
@validate_custom_event_count(count=0)
@background_task()
def test_gemini_chat_completion_sync_ai_monitoring_disabled(sync_gemini_client):
    sync_gemini_client.generate_content(
        _test_gemini_chat_completion_messages,
        generation_config=genai.types.GenerationConfig(
            temperature=0.7
        )
    )


@reset_core_stats_engine()
# One summary event, one system message, one user message, and one response message from the assistant
@validate_custom_event_count(count=3)
@validate_attributes("agent", ["llm"])
@background_task()
def test_gemini_chat_completion_sync_no_usage_data(set_trace_info, sync_gemini_client):
    # Only testing that there are events, and there was no exception raised
    set_trace_info()

    sync_gemini_client.generate_content(
        "No usage data",
        generation_config=genai.types.GenerationConfig(
            temperature=0.7
        )
    )


#@reset_core_stats_e
#def test_gemini_chat_completion_functions_marked_as_wrapped_for_sdk_compatibility():
#    assert genai._nr_wrapped
#    assert genai.util.convert_to_gemini_object._nr_wrapped