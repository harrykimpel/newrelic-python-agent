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

try:
    from django.core.wsgi import get_wsgi_application

    application = get_wsgi_application()

# This exception is to account for any users using Django v1.4 or earlier
except ImportError:
    import django.core.handlers.wsgi

    application = django.core.handlers.wsgi.WSGIHandler()