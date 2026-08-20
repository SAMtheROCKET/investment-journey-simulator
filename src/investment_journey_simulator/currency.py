"""Currencies, and the number habits that come with them.

A currency is not just a symbol in front of a figure. It carries how
the digits are grouped, what the magnitudes are called, and how many
minor units exist at all:

* **₹12,34,567** groups by two after the first three and counts in
  *lakh* and *crore*.
* **$1,234,567** groups by three and counts in *million*.
* **¥1,234,567** groups by three and has **no minor unit** - there
  are no sen in circulation, so a yen figure with two decimals is
  simply wrong.

Getting this right matters more than it looks. The interface echoes
every typed amount back in words so an extra zero is obvious, and
"12.35 lakh" shown against a dollar figure would be worse than
showing nothing at all.

Inflation defaults travel with the currency too, because a sensible
assumption in Mumbai is not a sensible one in Tokyo - but every one
of them is only a starting value the reader can overwrite.
"""

from __future__ import annotations

from dataclasses import dataclass

GROUPING_INDIAN_STR: str = "INDIAN"
GROUPING_WESTERN_STR: str = "WESTERN"

INDIAN_SCALE_TUPLE: tuple = (
    (10_000_000.0, "crore"),
    (100_000.0, "lakh"),
    (1_000.0, "thousand"),
)
WESTERN_SCALE_TUPLE: tuple = (
    (1_000_000_000.0, "billion"),
    (1_000_000.0, "million"),
    (1_000.0, "thousand"),
)

# Short suffixes for tiles and axis labels, where a full word will
# not fit. They follow the same rule as the long names: a rupee
# figure abbreviates to Cr and L, a dollar figure to B and M.
INDIAN_COMPACT_TUPLE: tuple = (
    (10_000_000.0, "Cr"),
    (100_000.0, "L"),
    (1_000.0, "K"),
)
WESTERN_COMPACT_TUPLE: tuple = (
    (1_000_000_000.0, "B"),
    (1_000_000.0, "M"),
    (1_000.0, "K"),
)


@dataclass(frozen=True)
class Currency:
    """One currency and the number habits that go with it."""

    code_str: str
    symbol_str: str
    name_str: str
    grouping_str: str = GROUPING_WESTERN_STR
    display_digits_int: int = 2
    default_inflation_percent_float: float = 2.0

    # display_digits_int is how many decimals to *show*, which is
    # not always how many the currency has. Yen genuinely has no
    # minor unit in circulation. Rupees do have paise, but no
    # figure in this program has ever displayed them, and a corpus
    # quoted to the paisa reads as false precision.

    @property
    def scale_tuple(self) -> tuple:
        """Magnitude names this currency counts in.

        Brief:
            Indian numbering counts in lakh and crore; almost
            everywhere else counts in million and billion.

        Arguments:
            None.

        Returns:
            tuple: Pairs of value and name, largest first.

        Warning:
            Naming a dollar figure in lakh would be worse than
            leaving it unnamed, so this must follow the currency.
        """
        if self.grouping_str == GROUPING_INDIAN_STR:
            return INDIAN_SCALE_TUPLE
        return WESTERN_SCALE_TUPLE

    @property
    def compact_tuple(self) -> tuple:
        """Short magnitude suffixes for tiles and axis labels.

        Brief:
            Follows the same rule as the long names, so a chart
            axis and the caption beneath it agree.

        Arguments:
            None.

        Returns:
            tuple: Pairs of value and suffix, largest first.

        Warning:
            "L" means lakh and only makes sense for a currency
            that counts in lakh.
        """
        if self.grouping_str == GROUPING_INDIAN_STR:
            return INDIAN_COMPACT_TUPLE
        return WESTERN_COMPACT_TUPLE

    @property
    def label_str(self) -> str:
        """How this currency is offered in a menu.

        Brief:
            Shows the code, the symbol and the name together, so a
            reader can find it by whichever one they know.

        Arguments:
            None.

        Returns:
            str: For example "INR ₹ - Indian rupee".

        Warning:
            Display only; the code is the identifier.
        """
        return (
            f"{self.code_str} {self.symbol_str} - {self.name_str}"
        )


# Symbols and codes are ISO 4217. The inflation figures are opening
# assumptions of the right order of magnitude for each economy, not
# forecasts and not sourced from any single publication - every one
# is overwritable, and the interface says so.
CURRENCY_TUPLE: tuple = (
    Currency(
        "INR", "₹", "Indian rupee", GROUPING_INDIAN_STR, 0, 6.0
    ),
    Currency(
        "USD", "$", "US dollar", GROUPING_WESTERN_STR, 2, 2.5
    ),
    Currency("EUR", "€", "Euro", GROUPING_WESTERN_STR, 2, 2.0),
    Currency(
        "GBP", "£", "Pound sterling", GROUPING_WESTERN_STR, 2, 2.5
    ),
    Currency(
        "JPY", "¥", "Japanese yen (円)", GROUPING_WESTERN_STR, 0, 1.0
    ),
    Currency(
        "CNY", "¥", "Chinese yuan (元)", GROUPING_WESTERN_STR, 2, 2.0
    ),
    Currency(
        "AUD", "A$", "Australian dollar", GROUPING_WESTERN_STR, 2, 2.5
    ),
    Currency(
        "CAD", "C$", "Canadian dollar", GROUPING_WESTERN_STR, 2, 2.0
    ),
    Currency(
        "SGD", "S$", "Singapore dollar", GROUPING_WESTERN_STR, 2, 2.0
    ),
    Currency(
        "CHF", "Fr", "Swiss franc", GROUPING_WESTERN_STR, 2, 1.0
    ),
    Currency(
        "AED", "د.إ", "UAE dirham", GROUPING_WESTERN_STR, 2, 2.0
    ),
)

DEFAULT_CURRENCY_CODE_STR: str = "INR"
CURRENCY_BY_CODE_DICT: dict[str, Currency] = {
    currency.code_str: currency for currency in CURRENCY_TUPLE
}


def resolve_currency(code_str: str = "") -> Currency:
    """Find a currency by its ISO code.

    Brief:
        Falls back to the rupee, which is what this program was
        built for and what every statutory rule in it assumes.

    Arguments:
        code_str (str): Three-letter ISO 4217 code.

    Returns:
        Currency: The currency, or the default when unknown.

    Warning:
        An unknown code is not an error. It silently means "use
        the default", so a stale saved scenario still opens.
    """
    return CURRENCY_BY_CODE_DICT.get(
        str(code_str).upper(),
        CURRENCY_BY_CODE_DICT[DEFAULT_CURRENCY_CODE_STR],
    )


def list_currency_code_list() -> list[str]:
    """Every currency code on offer, in menu order.

    Brief:
        The rupee comes first because it is the default and the
        only one whose tax rules ship fully modelled.

    Arguments:
        None.

    Returns:
        List[str]: ISO codes in display order.

    Warning:
        Order is presentational; the code is the identifier.
    """
    return [currency.code_str for currency in CURRENCY_TUPLE]


def group_digits_str(
    amount_float: float,
    grouping_str: str = GROUPING_INDIAN_STR,
    display_digits_int: int = 0,
) -> str:
    """Group digits the way a currency's readers expect.

    Brief:
        Indian grouping keeps the last three digits together and
        pairs everything before them; western grouping takes three
        at a time throughout.

    Arguments:
        amount_float (float): Amount to group.
        grouping_str (str): Which convention to use.
        display_digits_int (int): Decimal places to keep.

    Returns:
        str: Digit string with separators and a minus if negative.

    Warning:
        A currency with no minor unit is rounded to whole units,
        because writing yen to two decimals invents a coin that
        does not circulate.
    """
    rounded_float = round(
        float(amount_float), max(0, int(display_digits_int))
    )
    sign_str = "-" if rounded_float < 0 else ""
    absolute_float = abs(rounded_float)
    whole_int = int(absolute_float)
    fraction_str = _build_fraction_str(
        absolute_float, whole_int, display_digits_int
    )
    if grouping_str == GROUPING_INDIAN_STR:
        return sign_str + _group_indian_str(whole_int) + fraction_str
    return sign_str + f"{whole_int:,}" + fraction_str


def _build_fraction_str(
    absolute_float: float,
    whole_int: int,
    display_digits_int: int,
) -> str:
    """Render the decimal part, when the currency has one.

    Brief:
        Kept separate because whether a fraction exists at all is
        a property of the currency, not of the amount.

    Arguments:
        absolute_float (float): Amount without its sign.
        whole_int (int): Whole units of that amount.
        display_digits_int (int): Decimal places to keep.

    Returns:
        str: Decimal part including its point, or empty.

    Warning:
        Returns empty for a currency with no minor unit.
    """
    digits_int = max(0, int(display_digits_int))
    if digits_int <= 0:
        return ""
    fraction_float = absolute_float - whole_int
    return f"{fraction_float:.{digits_int}f}"[1:]


def _group_indian_str(whole_int: int) -> str:
    """Group whole units in the Indian style.

    Brief:
        Last three digits together, then pairs, so 1234567 becomes
        "12,34,567".

    Arguments:
        whole_int (int): Whole units, already non-negative.

    Returns:
        str: Grouped digit string.

    Warning:
        Expects a non-negative value; the sign is added by the
        caller.
    """
    digits_str = str(whole_int)
    if len(digits_str) <= 3:
        return digits_str
    head_str, tail_str = digits_str[:-3], digits_str[-3:]
    pair_list: list[str] = []
    while len(head_str) > 2:
        pair_list.append(head_str[-2:])
        head_str = head_str[:-2]
    if head_str:
        pair_list.append(head_str)
    return ",".join(reversed(pair_list)) + "," + tail_str


def format_money_str(
    amount_float: float,
    currency: Currency,
) -> str:
    """Render an amount with its symbol and grouping.

    Brief:
        The one function every display path should use, so a
        change of currency reaches the whole interface at once.

    Arguments:
        amount_float (float): Amount to render.
        currency (Currency): Currency it is denominated in.

    Returns:
        str: For example "₹12,34,567" or "$1,234,567.00".

    Warning:
        Display only; never parse this string back.
    """
    return currency.symbol_str + group_digits_str(
        amount_float,
        currency.grouping_str,
        currency.display_digits_int,
    )


def describe_money_str(
    amount_float: float,
    currency: Currency,
) -> str:
    """Say what an amount is, in digits and in its own words.

    Brief:
        Echoes a typed figure back named in the magnitudes that
        currency actually counts in - lakh and crore for rupees,
        million and billion elsewhere.

    Arguments:
        amount_float (float): Amount to describe.
        currency (Currency): Currency it is denominated in.

    Returns:
        str: For example "₹2,00,000 - 2.00 lakh".

    Warning:
        Amounts below the smallest named magnitude are given
        plainly, because naming them adds nothing.
    """
    grouped_str = format_money_str(amount_float, currency)
    absolute_float = abs(float(amount_float))
    for scale_float, scale_name_str in currency.scale_tuple:
        if absolute_float >= scale_float:
            scaled_float = absolute_float / scale_float
            return (
                f"{grouped_str} - {scaled_float:.2f} "
                f"{scale_name_str}"
            )
    return grouped_str
