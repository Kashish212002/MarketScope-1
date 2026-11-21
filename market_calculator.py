def calculate_cagr(start_value, end_value, years):
    """Calculate compound annual growth rate."""

    if start_value <= 0 or end_value < 0 or years <= 0:
        raise ValueError("Invalid CAGR inputs.")

    return (end_value / start_value) ** (1 / years) - 1


def forecast_market(current_value, annual_growth_rate, years):
    """Project market value using an annual growth rate."""

    return [
        {
            "year": year,
            "market_value": current_value * (
                1 + annual_growth_rate
            ) ** year
        }
        for year in range(1, years + 1)
    ]


def calculate_bottom_up(volume, price_per_unit):
    """Calculate market value using volume multiplied by price."""

    return volume * price_per_unit


def calculate_gpu_market(
    gpu_count,
    hours_per_day,
    utilisation,
    price_per_hour,
    operating_days=365
):
    """
    Estimate annual GPUaaS revenue.

    Revenue = GPU count × available hours × utilisation
              × realised hourly price
    """

    annual_hours = hours_per_day * operating_days

    revenue = (
        gpu_count
        * annual_hours
        * utilisation
        * price_per_hour
    )

    return revenue


def calculate_tam_sam_som(
    tam,
    sam_percentage,
    som_percentage
):
    """Calculate TAM, SAM and SOM."""

    sam = tam * sam_percentage
    som = sam * som_percentage

    return {
        "TAM": tam,
        "SAM": sam,
        "SOM": som
    }


def scenario_forecast(
    current_value,
    years,
    downside_growth,
    base_growth,
    upside_growth
):
    """Generate three independent forecast scenarios."""

    scenarios = {
        "Downside": downside_growth,
        "Base": base_growth,
        "Upside": upside_growth
    }

    results = {}

    for scenario, growth_rate in scenarios.items():

        results[scenario] = [
            {
                "year": year,
                "market_value": current_value * (
                    1 + growth_rate
                ) ** year
            }
            for year in range(1, years + 1)
        ]

    return results


if __name__ == "__main__":

    print("MARKETSCOPE CALCULATION ENGINE")
    print("=" * 40)

    # Illustrative GPUaaS assumptions only
    annual_revenue = calculate_gpu_market(
        gpu_count=1000,
        hours_per_day=24,
        utilisation=0.65,
        price_per_hour=2.0
    )

    print("Illustrative annual GPUaaS revenue:", annual_revenue)

    forecasts = scenario_forecast(
        current_value=annual_revenue,
        years=5,
        downside_growth=0.15,
        base_growth=0.25,
        upside_growth=0.35
    )

    print("\nFive-year illustrative scenarios:")

    for scenario, values in forecasts.items():
        print(f"\n{scenario} scenario:")

        for item in values:
            print(item)