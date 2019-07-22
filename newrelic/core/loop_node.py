from collections import namedtuple

import newrelic.core.trace_node

from newrelic.core.node_mixin import GenericNodeMixin
from newrelic.core.metric import TimeMetric

_LoopNode = namedtuple('_LoopNode',
        ['fetch_name', 'start_time', 'end_time', 'duration', 'guid'])


class LoopNode(_LoopNode, GenericNodeMixin):

    @property
    def exclusive(self):
        return self.duration

    @property
    def agent_attributes(self):
        return {}

    @property
    def children(self):
        return ()

    @property
    def name(self):
        return self.fetch_name()

    def time_metrics(self, stats, root, parent):
        """Return a generator yielding the timed metrics for this
        function node as well as all the child nodes.

        """

        name = 'IoLoop/Wait/%s' % self.name

        yield TimeMetric(name=name, scope='', duration=self.duration,
                exclusive=self.duration)

        yield TimeMetric(name=name, scope=root.path,
                duration=self.duration, exclusive=self.duration)

        name = 'IoLoop/Wait/all'

        # Create IO loop rollup metrics
        yield TimeMetric(name=name, scope='', duration=self.duration,
                exclusive=None)

        if root.type == 'WebTransaction':
            yield TimeMetric(name=name + 'Web', scope='',
                    duration=self.duration, exclusive=None)
        else:
            yield TimeMetric(name=name + 'Other', scope='',
                    duration=self.duration, exclusive=None)

    def trace_node(self, stats, root, connections):

        name = 'IoLoop/Wait/%s' % self.name

        name = root.string_table.cache(name)

        start_time = newrelic.core.trace_node.node_start_time(root, self)
        end_time = newrelic.core.trace_node.node_end_time(root, self)

        root.trace_node_count += 1

        children = []

        # Agent attributes
        params = {
            'exclusive_duration_millis': 1000.0 * self.duration,
        }

        return newrelic.core.trace_node.TraceNode(start_time=start_time,
                end_time=end_time, name=name, params=params, children=children,
                label=None)

    def span_event(self, *args, **kwargs):
        attrs = super(LoopNode, self).span_event(*args, **kwargs)
        i_attrs = attrs[0]

        i_attrs['name'] = 'IoLoop/Wait/%s' % self.name

        return attrs
