import sys
import logging
import click
from typing import Optional

logger = logging.getLogger(__name__)

@click.command()
@click.option('--days', '-d', default=3, help='Number of days to show (default: 3)')
@click.option('--project', '-p', help='GCP project ID (defaults to GOOGLE_CLOUD_PROJECT env var)')
def cloud_usage(days: int, project: Optional[str]):
    """Display Firestore usage from Cloud Monitoring.

    Shows Firestore read/write operations vs free tier limits.
    Requires google-cloud-monitoring package and GCP credentials.

    Requirements: 4.3

    Examples:
      mhl.py cloud-usage              # Show last 3 days
      mhl.py cloud-usage --days 7     # Show last 7 days
      mhl.py cloud-usage -p my-proj   # Specify project ID
    """
    import os
    from datetime import datetime, timedelta

    # Determine project ID
    project_id = project or os.environ.get('GOOGLE_CLOUD_PROJECT') or os.environ.get('GCP_PROJECT')

    if not project_id:
        click.echo("Error: No GCP project ID specified.", err=True)
        click.echo("Set GOOGLE_CLOUD_PROJECT environment variable or use --project flag.", err=True)
        sys.exit(1)

    click.echo(f"\nFirestore Usage Report - Project: {project_id}")
    click.echo("=" * 70)

    try:
        from google.cloud import monitoring_v3
        from google.protobuf.timestamp_pb2 import Timestamp
    except ImportError:
        click.echo("Error: google-cloud-monitoring package not installed.", err=True)
        click.echo("Install with: pip install google-cloud-monitoring", err=True)
        sys.exit(1)

    try:
        client = monitoring_v3.MetricServiceClient()
        project_name = f"projects/{project_id}"

        # Time range
        now = datetime.utcnow()
        start_time = now - timedelta(days=days)

        # Free tier limits
        FREE_TIER_READS = 50_000
        FREE_TIER_WRITES = 20_000

        click.echo(f"\nFree Tier Limits (per day):")
        click.echo(f"  Reads:  {FREE_TIER_READS:,}")
        click.echo(f"  Writes: {FREE_TIER_WRITES:,}")
        click.echo()

        # Query Firestore document reads
        click.echo(f"Fetching usage data for last {days} days...")
        click.echo()

        # Build the time interval using protobuf Timestamp
        from google.protobuf import timestamp_pb2
        end_time = timestamp_pb2.Timestamp()
        end_time.seconds = int(now.timestamp())
        start_time_pb = timestamp_pb2.Timestamp()
        start_time_pb.seconds = int(start_time.timestamp())

        interval = monitoring_v3.TimeInterval(
            end_time=end_time,
            start_time=start_time_pb
        )

        # Aggregation: sum per day
        from google.protobuf import duration_pb2
        alignment_period = duration_pb2.Duration(seconds=86400)  # 1 day

        aggregation = monitoring_v3.Aggregation(
            alignment_period=alignment_period,
            per_series_aligner=monitoring_v3.Aggregation.Aligner.ALIGN_SUM,
            cross_series_reducer=monitoring_v3.Aggregation.Reducer.REDUCE_SUM,
            group_by_fields=["resource.labels.database_id"]
        )

        # Query document reads
        # Use firestore.googleapis.com/document/read_count metric
        reads_filter = 'metric.type="firestore.googleapis.com/document/read_count"'

        reads_by_date: dict[str, int] = {}
        writes_by_date: dict[str, int] = {}

        try:
            reads_results = client.list_time_series(
                request={
                    "name": project_name,
                    "filter": reads_filter,
                    "interval": interval,
                    "aggregation": aggregation,
                    "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                }
            )

            for series in reads_results:
                for point in series.points:
                    # Handle both protobuf Timestamp and DatetimeWithNanoseconds
                    end_time = point.interval.end_time
                    if hasattr(end_time, 'seconds'):
                        date_str = datetime.utcfromtimestamp(end_time.seconds).strftime('%Y-%m-%d')
                    else:
                        # DatetimeWithNanoseconds is already a datetime
                        date_str = end_time.strftime('%Y-%m-%d')
                    reads_by_date[date_str] = reads_by_date.get(date_str, 0) + int(point.value.int64_value)
        except Exception as e:
            logger.warning(f"Could not fetch read metrics: {e}")

        # Query document writes
        writes_filter = 'metric.type="firestore.googleapis.com/document/write_count"'

        try:
            writes_results = client.list_time_series(
                request={
                    "name": project_name,
                    "filter": writes_filter,
                    "interval": interval,
                    "aggregation": aggregation,
                    "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                }
            )

            for series in writes_results:
                for point in series.points:
                    # Handle both protobuf Timestamp and DatetimeWithNanoseconds
                    end_time = point.interval.end_time
                    if hasattr(end_time, 'seconds'):
                        date_str = datetime.utcfromtimestamp(end_time.seconds).strftime('%Y-%m-%d')
                    else:
                        # DatetimeWithNanoseconds is already a datetime
                        date_str = end_time.strftime('%Y-%m-%d')
                    writes_by_date[date_str] = writes_by_date.get(date_str, 0) + int(point.value.int64_value)
        except Exception as e:
            logger.warning(f"Could not fetch write metrics: {e}")

        # Display results
        if not reads_by_date and not writes_by_date:
            click.echo("No usage data found for the specified period.")
            click.echo("This could mean:")
            click.echo("  - No Firestore operations occurred")
            click.echo("  - Metrics are not yet available (can take up to 4 hours)")
            click.echo("  - The project ID is incorrect")
            sys.exit(0)

        # Get all dates
        all_dates = sorted(set(reads_by_date.keys()) | set(writes_by_date.keys()), reverse=True)

        click.echo(f"{'Date':<12} {'Reads':>12} {'% Free':>10} {'Writes':>12} {'% Free':>10} {'Status':<10}")
        click.echo("-" * 70)

        for date in all_dates:
            reads = reads_by_date.get(date, 0)
            writes = writes_by_date.get(date, 0)

            reads_pct = (reads / FREE_TIER_READS) * 100
            writes_pct = (writes / FREE_TIER_WRITES) * 100

            # Determine status
            if reads > FREE_TIER_READS or writes > FREE_TIER_WRITES:
                status = "⚠️  OVER"
            elif reads > FREE_TIER_READS * 0.8 or writes > FREE_TIER_WRITES * 0.8:
                status = "⚡ WARNING"
            else:
                status = "✅ OK"

            click.echo(
                f"{date:<12} {reads:>12,} {reads_pct:>9.1f}% "
                f"{writes:>12,} {writes_pct:>9.1f}% {status:<10}"
            )

        click.echo("-" * 70)

        # Summary
        total_reads = sum(reads_by_date.values())
        total_writes = sum(writes_by_date.values())
        avg_reads = total_reads / len(all_dates) if all_dates else 0
        avg_writes = total_writes / len(all_dates) if all_dates else 0

        click.echo()
        click.echo(f"Summary ({len(all_dates)} days):")
        click.echo(f"  Average daily reads:  {avg_reads:,.0f} ({(avg_reads/FREE_TIER_READS)*100:.1f}% of free tier)")
        click.echo(f"  Average daily writes: {avg_writes:,.0f} ({(avg_writes/FREE_TIER_WRITES)*100:.1f}% of free tier)")

        # Recommendations
        click.echo()
        if avg_reads > FREE_TIER_READS:
            click.echo("⚠️  ALERT: Average reads exceed free tier limit!")
            click.echo("   Consider reducing sync frequency or optimizing queries.")
        elif avg_reads > FREE_TIER_READS * 0.8:
            click.echo("⚡ WARNING: Average reads approaching free tier limit.")
        else:
            click.echo("✅ Usage is within free tier limits.")

        click.echo()

    except Exception as e:
        click.echo(f"Error querying Cloud Monitoring: {e}", err=True)
        logger.error(f"Cloud Monitoring query failed: {e}", exc_info=True)
        sys.exit(1)
