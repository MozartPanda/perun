"""``perun.profile.query`` is a module which specifies interface for issuing
queries over the profiles w.r.t :ref:`profile-spec`.

.. _Pandas library: https://docs.python.org/3.7/library/json.html

Run the following in the Python interpreter to extend the capabilities of
profile to query over profiles, iterate over resources or models, etc.::

    import perun.profile.query

Combined with ``perun.profile.factory``, ``perun.profile.convert`` and e.g.
`Pandas library`_ one can obtain efficient interpreter for executing more
complex queries and statistical tests over the profiles.
"""

from __future__ import annotations

# Standard Imports
from typing import Any, TYPE_CHECKING, Iterable
import numbers
import operator

# Third-Party Imports

# Perun Imports
from perun.utils.common import common_kit

if TYPE_CHECKING:
    from perun.profile import Profile


def flattened_values(root_key: Any, root_value: Any) -> Iterable[tuple[str, str | float]]:
    """Converts the (root_key, root_value) pair to something that can be added to table.

    Flattens all the dictionaries to single level and <key>(:<key>)? values, lists are processed
    to comma separated representation and rest is left as it is.

    :param root_key: name (or index) of the processed key, that is going to be flattened
    :param root_value: value that is flattened
    :return: either decimal, string, or something else
    """
    # Dictionary is processed recursively according to the all items that are nested
    if isinstance(root_value, dict):
        nested_values = []
        for key, value in all_items_of(root_value):
            # Add one level of hierarchy with ':'
            nested_values.append((key, value))
            yield str(root_key) + ":" + key, value
        # Additionally return the overall key as joined values of its nested stuff,
        # only if root is not a list (i.e. root key is not int = index)!
        if isinstance(root_key, str):
            nested_values.sort(key=common_kit.uid_getter)
            yield root_key, ":".join(map(str, map(operator.itemgetter(1), nested_values)))
    elif isinstance(root_value, list):
        # Lists that represent variable length dictionary
        if common_kit.is_variable_len_dict(root_value):
            dictionary = {v["name"]: v["value"] for v in root_value}
            yield from flattened_values(root_key, dictionary)
        # Lists are merged as comma separated keys
        else:
            yield root_key, ",".join(
                ":".join(str(nested_value[1]) for nested_value in flattened_values(i, lv))
                for (i, lv) in enumerate(root_value)
            )
    # Rest of the values are left as they are
    else:
        yield root_key, root_value


def all_items_of(resource: dict[str, Any]) -> Iterable[tuple[str, str | float]]:
    """Generator for iterating through the flattened items contained
    inside the resource w.r.t :pkey:`resources` specification.

    Generator iterates through the items contained in the `resource` in
    flattened form (i.e. it does not contain nested dictionaries). Resources
    should be w.r.t :pkey:`resources` specification.

    E.g. the following resource:

    .. code-block:: json

        {
            "type": "memory",
            "amount": 4,
            "uid": {
                "source": "../memory_collect_test.c",
                "function": "main",
                "line": 22
            }
        }

    yields the following stream of resources::

        ("type", "memory")
        ("amount", 4)
        ("uid", "../memory_collect_test.c:main:22")
        ("uid:source", "../memory_collect_test.c")
        ("uid:function", "main")
        ("uid:line": 22)

    :param resource: dictionary representing one resource
        w.r.t :pkey:`resources`
    :returns: iterable stream of ``(str, value)`` pairs, where the ``value`` is
        flattened to either a `string`, or `decimal` representation and ``str``
        corresponds to the key of the item
    """
    for key, value in resource.items():
        for flattened_key, flattened_value in flattened_values(key, value):
            yield flattened_key, flattened_value


def all_model_fields_of(profile: Profile) -> Iterable[str]:
    """Generator for iterating through all the fields (both flattened and
    original) that are occurring in the models.

    E.g. considering the example profiles from :ref:`postprocessors-regression-analysis`, the function
    yields the following model keys:

        model_keys = ['coeffs:b1', 'coeffs:b0', 'coeffs', 'r_square', 'x_interval_end', 'model', 'method', 'uid',
            'x_interval_start', 'coeffs:b2']
        memory_resource_fields = [
            'type', 'address', 'amount', 'uid:function', 'uid:source',
            'uid:line', 'uid', 'trace', 'subtype'
        ]

    :param profile: performance profile w.r.t :ref:`profile-spec`
    :returns: iterable stream of model field keys represented as `str`
    """
    yield from _all_fields_of(profile.all_models())


def _all_fields_of(item_generator: Iterable[tuple[int, dict[str, Any]]]) -> Iterable[str]:
    """Helper generator for iterating through all the fields generated by the item_generator

    Generator iterates through all the resources and checks their flattened
    keys. In case some of the keys were not yet processed, they are yielded.

    :param item_generator: iterable stream of items
    :return: iterable stream of field keys represented as `str`
    """
    resource_fields = set()
    for _, resource in item_generator:
        for key, __ in all_items_of(resource):
            if key not in resource_fields:
                resource_fields.add(key)
                yield key


def all_numerical_resource_fields_of(profile: Profile) -> Iterable[str]:
    """Generator for iterating through all the fields (both flattened and
    original) that are occurring in the resources and takes as domain integer
    values.

    Generator iterates through all the resources and checks their flattened
    keys and yields them in case they were not yet processed. If the instance
    of the key does not contain integer values, it is skipped.

    E.g. considering the example profiles from :pkey:`resources`, the function
    yields the following for `memory`, `time` and `trace` profiles
    respectively (considering we convert the stream to list)::

        memory_num_resource_fields = ['address', 'amount', 'uid:line']
        time_num_resource_fields = ['amount']
        complexity_num_resource_fields = ['amount', 'structure-unit-size']

    :param profile: performance profile w.r.t :ref:`profile-spec`
    :returns: iterable stream of resource fields key as `str`, that takes integer values
    """
    resource_fields = set()
    exclude_fields = set()
    for _, resource in profile.all_resources():
        for key, value in all_items_of(resource):
            # Instances that are not numbers are removed from the resource fields (i.e. there was
            # some inconsistency between value) and added to exclude for future usages
            if not isinstance(value, numbers.Number):
                resource_fields.discard(key)
                exclude_fields.add(key)
            # If we previously encountered incorrect non-numeric value for the key, we do not add
            # it as a numeric key
            elif value not in exclude_fields:
                resource_fields.add(key)

    # Yield the stream of the keys
    for key in resource_fields:
        yield key


def unique_resource_values_of(profile: Profile, resource_key: str) -> Iterable[str]:
    """Generator of all unique key values occurring in the resources, w.r.t.
    :pkey:`resources` specification of resources.

    Iterates through all the values of given ``resource_keys`` and yields
    only unique values. Note that the key can contain ':' symbol indicating
    another level of dictionary hierarchy or '::' for specifying keys in list
    or set level, e.g. in case of `traces` one uses ``trace::function``.

    E.g. considering the example profiles from :pkey:`resources`, the function
    yields the following for `memory`, `time` and `trace` profiles stored
    in variables ``mprof``, ``tprof`` and ``cprof`` respectively::

        >>> list(query.unique_resource_values_of(mprof, 'subtype')
        ['malloc', 'free']
        >>> list(query.unique_resource_values_of(tprof, 'amount')
        [0.616, 0.500, 0.125]
        >>> list(query.unique_resource_values_of(cprof, 'uid')
        ['SLList_init(SLList*)', 'SLList_search(SLList*, int)',
         'SLList_insert(SLList*, int)', 'SLList_destroy(SLList*)']

    :param profile: performance profile w.r.t :ref:`profile-spec`
    :param resource_key: the resources key identifier whose unique values
        will be iterated
    :returns: iterable stream of unique resource key values
    """
    for value in _unique_values_generator(resource_key, profile.all_resources()):
        yield value


def all_key_values_of(resource: dict[str, Any], resource_key: str) -> Iterable[Any]:
    """Generator of all (not essentially unique) key values in resource, w.r.t
    :pkey:`resources` specification of resources.

    Iterates through the values of given ``resource_key`` and yields
    every value it finds. Note that the key can contain ':' symbol indicating
    another level of dictionary hierarchy or '::' for specifying keys in list
    or set level, e.g. in case of `traces` one uses ``trace::function``.

    E.g. considering the example profiles from :pkey:`resources` and the
    resources ``mres`` from the profile of `memory` type, we can obtain
    the values of ``trace::function`` key as follows::

        >>> query.all_key_values_of(mres, 'trace::function')
        ['free', 'main', '__libc_start_main', '_start']

    Note that this is mostly useful for iterating through list or nested
    dictionaries.

    :param resource: dictionary representing one resource
        w.r.t :pkey:`resources`
    :param resource_key: the resources key identifier whose unique values
        will be iterated
    :returns: iterable stream of all resource key values
    """
    # Convert the key identifier to iterable hierarchy
    key_hierarchy = resource_key.split(":")

    # Iterate the hierarchy
    for level_idx, key_level in enumerate(key_hierarchy):
        if key_level == "" and isinstance(resource, (list, set)):
            # The level is list, iterate all the members recursively
            for item in resource:
                for result in all_key_values_of(item, ":".join(key_hierarchy[level_idx + 1 :])):
                    yield result
            return
        elif key_level in resource:
            # The level is dict, find key
            resource = resource[key_level]
        else:
            # No match
            return
    yield resource


def unique_model_values_of(profile: Profile, model_key: str) -> Iterable[Any]:
    """Generator of all unique key values occurring in the models in the
    resources of given performance profile w.r.t. :ref:`profile-spec`.

    Iterates through the values of given ``resource_keys`` and yields
    only unique values. Note that the key can contain ':' symbol indicating
    another level of dictionary hierarchy or '::' for specifying keys in list
    or set level, e.g. in case of `traces` one uses ``trace::function``.  For
    more details about the specification of models refer to :pkey:`models` or
    :ref:`postprocessors-regression-analysis`.

    E.g. given some trace profile ``complexity_prof``, we can obtain
    unique values of keys from `models` as follows:

        >>> list(query.unique_model_values_of('model'))
        ['constant', 'exponential', 'linear', 'logarithmic', 'quadratic']
        >>> list(query.unique_model_values_of('r_square'))
        [0.0, 0.007076437903106431, 0.0017560012128507133,
         0.0008704119815403224, 0.003480627284909902, 0.001977866710139782,
         0.8391363620083871, 0.9840099999298596, 0.7283427343995424,
         0.9709120064750161, 0.9305786182556899]

    :param profile: performance profile w.r.t :ref:`profile-spec`
    :param model_key: key identifier from `models` for which we query
        its unique values
    :returns: iterable stream of unique model key values
    """
    for value in _unique_values_generator(model_key, profile.all_models()):
        yield value


def _unique_values_generator(key: str, blocks_gen: Iterable[tuple[Any, dict[str, Any]]]) -> Any:
    """Generator of all unique values of 'key' occurring in the profile blocks generated by 'blocks_gen'.

    :param key: the key identifier whose unique values are returned
    :param blocks_gen: the data blocks generator (e.g. all_resources of Profile)
    :return: stream of unique key values
    """
    # value can be dict, list, set etc. and not only simple type, thus the list
    unique_values = list()
    for _, resource in blocks_gen:
        # Get all values the key contains
        for value in all_key_values_of(resource, key):
            # Return only the unique ones
            if value not in unique_values:
                unique_values.append(value)
                yield value
