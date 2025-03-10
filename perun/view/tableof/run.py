"""Table interpretation of the profile"""

from __future__ import annotations

# Standard Imports
from itertools import groupby
from typing import Callable, Any
import operator
import os

# Third-Party Imports
import click
import pandas
import tabulate

# Perun Imports
from perun.utils import log
from perun.profile import convert, query, helpers
from perun.profile.factory import Profile


def get_headers(ctx: click.Context) -> list[str]:
    """According to the loaded profile, checks the list of possible keys that can be used for
    filtering, sorting, etc.

    :param ctx: context of the called click
    :return: candidate headers for resources or models
    """
    headers = []
    assert (
        ctx.command is not None and ctx.parent is not None and ctx.parent.parent is not None
    ), "internal click error: ctx.command, ctx.parent or ctx.parent.parent is None"
    if ctx.command.name == "resources":
        headers = list(ctx.parent.parent.params["profile"].all_resource_fields()) + ["snapshots"]
    elif ctx.command.name == "models":
        headers = list(query.all_model_fields_of(ctx.parent.parent.params["profile"]))
    return headers


def output_table_to(table: str, target: str, target_file: str) -> None:
    """Outputs the table either to stdout or file

    :param table: outputted table
    :param target: either file or stdout
    :param target_file: name of the output file
    """
    if target == "file":
        with open(target_file, "w") as wtf:
            wtf.write(table)
    else:
        log.write(table)


def create_table_from(
    profile: Profile,
    conversion_function: Callable[[Profile], pandas.DataFrame],
    headers: list[str],
    tablefmt: str,
    sort_by: str,
    filter_by: list[tuple[str, str]],
) -> str:
    """Using the tabulate package, transforms the profile into table.

    Currently, the representation contains all possible keys.

    :param profile: profile transformed into the table
    :param conversion_function: function that converts profile to table
    :param headers: list of headers of the table
    :param sort_by: key for which we will sort
    :param filter_by: list of keys that will be potentially filtered
    :param tablefmt: format of the table
    :param filter_by: key by which we filter
    :return: tabular representation of the profile in string
    """
    dataframe = conversion_function(profile)

    # Sort the dataframe inplace (to modify the values)
    if sort_by:
        dataframe.sort_values(sort_by, inplace=True)

    # Filter the values according to set rules
    if filter_by:
        groups = [(k, list(v)) for (k, v) in groupby(filter_by, operator.itemgetter(0))]
        filter_query = " & ".join(
            '@dataframe.get("{0}") in [{1}]'.format(
                key, ", ".join(f'"{v[1]}"' for v in list(value))
            )
            for (key, value) in groups
        )
        dataframe.query(filter_query, inplace=True)

    resource_table = dataframe[headers].values.tolist()
    return tabulate.tabulate(resource_table, headers=headers, tablefmt=tablefmt)


def process_filter(ctx: click.Context, option: click.Option, value: list[str]) -> list[str]:
    """Processes option for filtering of the table, according to the profile keys

    :param ctx: context of the called command
    :param option: called option
    :param value: list of (key, value) tuples
    :return: valid filtering keys
    """
    headers = get_headers(ctx)

    if value:
        for val in value:
            if val[0] not in headers:
                raise click.BadOptionUsage(
                    option.name or "",
                    (
                        f"invalid key choice for filtering: {val[0]} (choose from"
                        f" {', '.join(headers)})"
                    ),
                )
        return list(value)
    return value


def process_sort_key(ctx: click.Context, option: click.Option, value: str) -> str:
    """Processes the key for sorting the table

    :param ctx: context of the called command
    :param option: called option
    :param value: key used for sorting
    :return: valid key for sorting
    """
    headers = get_headers(ctx)

    if value and value not in headers:
        raise click.BadOptionUsage(
            option.name or "",
            f"invalid key choice for sorting the table: {value} (choose from {', '.join(headers)})",
        )
    return value


def process_headers(ctx: click.Context, option: click.Option, value: list[str]) -> list[str]:
    """Processes list of headers of the outputted table

    :param ctx: context of the called command
    :param option: called option
    :param value: tuple of stated header keys
    :return: list of headers of the table
    """
    headers = get_headers(ctx)

    # In case something was stated in the CLI we use these headers
    if value:
        for val in value:
            if val not in headers:
                raise click.BadOptionUsage(
                    option.name or "",
                    f"invalid choice for table header: {val} (choose from {', '.join(headers)})",
                )
        return list(value)
    # Else we output everything
    else:
        return sorted(headers)


def process_output_file(ctx: click.Context, _: click.Option, value: str) -> str:
    """Generates the name of the output file, if no value is issued

    If no output file is set, then we generate the profile name according to the profile
    and append the "resources_of" or "models_of" prefix to the file.

    :param ctx: context of the called command
    :param _: called option
    :param value: output file of the show
    :return: output file of the show
    """
    assert ctx.parent is not None and f"impossible happened: {ctx} has no parent"
    if value:
        return value
    else:
        prof_name = helpers.generate_profile_name(ctx.parent.params["profile"])
        return (
            (ctx.command.name or "<MISSING_COMMAND_NAME>") + "_of_" + os.path.splitext(prof_name)[0]
        )


@click.group()
@click.option(
    "--to-file",
    "-tf",
    "output_to",
    flag_value="file",
    help=(
        "The table will be saved into a file. By default, the name of the output file"
        " is automatically generated, unless `--output-file` option does not specify"
        " the name of the output file."
    ),
    default=True,
)
@click.option(
    "--to-stdout",
    "-ts",
    "output_to",
    flag_value="stdout",
    help="The table will be output to standard output.",
)
@click.option(
    "--output-file",
    "-of",
    default=None,
    callback=process_output_file,
    help="Target output file, where the transformed table will be saved.",
)
@click.option(
    "--format",
    "-f",
    "tablefmt",
    default="simple",
    type=click.Choice(tabulate.tabulate_formats),
    help="Format of the outputted table",
)
@click.pass_context
def tableof(*_: Any, **__: Any) -> None:
    """Textual representation of the profile as a table.

    .. _tabulate: https://pypi.org/project/tabulate/

    \b
      * **Limitations**: `none`.
      * **Interpretation style**: textual
      * **Visualization backend**: tabulate_

    The table is formatted using the tabulate_ library. Currently, we support only the simplest
    form, and allow output to file.

    The example output of the tableof is as follows::

        \b

            uid                          model           r_square
            ---------------------------  -----------  -----------
            SLlist_insert(SLlist*, int)  logarithmic  0.000870412
            SLlist_insert(SLlist*, int)  linear       0.001756
            SLlist_insert(SLlist*, int)  quadratic    0.00199925
            SLlist_insert(SLlist*, int)  power        0.00348063
            SLlist_insert(SLlist*, int)  exponential  0.00707644
            SLlist_search(SLlist*, int)  constant     0.0114714
            SLlist_search(SLlist*, int)  logarithmic  0.728343
            SLlist_search(SLlist*, int)  exponential  0.839136
            SLlist_search(SLlist*, int)  power        0.970912
            SLlist_search(SLlist*, int)  linear       0.98401
            SLlist_search(SLlist*, int)  quadratic    0.984263
            SLlist_insert(SLlist*, int)  constant     1

    Refer to :ref:`views-tableof` for more thorough description and example of
    `table` interpretation possibilities.
    """
    pass


@tableof.command()
@click.option(
    "--headers",
    "-h",
    default=None,
    multiple=True,
    metavar="<key>",
    callback=process_headers,
    help=(
        "Sets the headers that will be displayed in the table. If none are stated "
        "then all of the headers will be output"
    ),
)
@click.option(
    "--sort-by",
    "-s",
    default=None,
    metavar="<key>",
    callback=process_sort_key,
    help="Sorts the table by <key>.",
)
@click.option(
    "--filter-by",
    "-f",
    "filter_by",
    nargs=2,
    metavar="<key> <value>",
    callback=process_filter,
    multiple=True,
    help=(
        "Filters the table to rows, where <key> == <value>. If the `--filter` is set"
        " several times, then rows satisfying all rules will be selected for different"
        " keys; and the rows satisfying some rule will be selected for same key."
    ),
)
@click.pass_context
def resources(
    ctx: click.Context,
    headers: list[str],
    sort_by: str,
    filter_by: list[tuple[str, str]],
    **_: Any,
) -> None:
    """Outputs the resources of the profile as a table"""
    assert ctx.parent is not None and f"impossible happened: {ctx} has no parent"
    assert ctx.parent.parent is not None and f"impossible happened: {ctx.parent} has no parent"

    tablefmt = ctx.parent.params["tablefmt"]
    profile = ctx.parent.parent.params["profile"]
    profile_as_table = create_table_from(
        profile,
        convert.resources_to_pandas_dataframe,
        headers,
        tablefmt,
        sort_by,
        filter_by,
    )
    output_table_to(
        profile_as_table,
        ctx.parent.params["output_to"],
        ctx.parent.params["output_file"],
    )


@tableof.command()
@click.pass_context
@click.option(
    "--headers",
    "-h",
    default=None,
    multiple=True,
    metavar="<key>",
    callback=process_headers,
    help=(
        "Sets the headers that will be displayed in the table. If none are stated "
        "then all of the headers will be output"
    ),
)
@click.option(
    "--sort-by",
    "-s",
    default=None,
    metavar="<key>",
    callback=process_sort_key,
    help="Sorts the table by <key>.",
)
@click.option(
    "--filter-by",
    "-f",
    "filter_by",
    nargs=2,
    metavar="<key> <value>",
    callback=process_filter,
    multiple=True,
    help=(
        "Filters the table to rows, where <key> == <value>. If the `--filter` is set"
        " several times, then rows satisfying all rules will be selected for different"
        " keys; and the rows satisfying some rule will be selected for same key."
    ),
)
def models(
    ctx: click.Context,
    headers: list[str],
    sort_by: str,
    filter_by: list[tuple[str, str]],
    **_: Any,
) -> None:
    """Outputs the models of the profile as a table"""
    assert ctx.parent is not None and f"impossible happened: {ctx} has no parent"
    assert ctx.parent.parent is not None and f"impossible happened: {ctx.parent} has no parent"

    tablefmt = ctx.parent.params["tablefmt"]
    profile = ctx.parent.parent.params["profile"]
    profile_as_table = create_table_from(
        profile,
        convert.models_to_pandas_dataframe,
        headers,
        tablefmt,
        sort_by,
        filter_by,
    )
    output_table_to(
        profile_as_table,
        ctx.parent.params["output_to"],
        ctx.parent.params["output_file"],
    )
