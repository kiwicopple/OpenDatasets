#!/usr/bin/env python3
"""
Create a sample DuckDB database with PostgreSQL mailing list structure.
Uses realistic sample data to demonstrate the schema.
"""

import duckdb
from datetime import datetime, timedelta
import random

DATABASE_PATH = "postgres_mailing_lists.duckdb"

# Sample data representing real pgsql-hackers emails
SAMPLE_MESSAGES = [
    {
        "id": "CAFj8pRA1bvVXZBPgP2qT_p-01@mail.gmail.com",
        "message_id": "<CAFj8pRA1bvVXZBPgP2qT_p-01@mail.gmail.com>",
        "subject": "Re: Proposal: Add support for incremental materialized view maintenance",
        "author": "Tom Lane <tgl@sss.pgh.pa.us>",
        "date": "2024-12-15 14:32:00",
        "content": """I've been thinking about this proposal some more.

The main challenge with incremental materialized view maintenance is handling
complex queries with aggregates and joins. We'd need to track deltas at each
stage of the query plan.

For simple cases (single table, no aggregates), this should be straightforward.
The tricky part is when you have:

1. Joins - need to maintain auxiliary data structures
2. Aggregates - need to handle both insertions and deletions
3. Subqueries - especially correlated ones

I think we should start with a limited subset of query types and expand
from there. Thoughts?

--
Tom Lane
PostgreSQL Development Team""",
        "thread_id": "incremental-matview-01",
    },
    {
        "id": "20241215.183045.12345@postgresql.org",
        "message_id": "<20241215.183045.12345@postgresql.org>",
        "subject": "Re: Proposal: Add support for incremental materialized view maintenance",
        "author": "Andres Freund <andres@anarazel.de>",
        "date": "2024-12-15 18:30:45",
        "content": """On 2024-12-15, Tom Lane wrote:
> The main challenge with incremental materialized view maintenance is handling
> complex queries with aggregates and joins.

Agreed. I've looked at how other databases handle this:

- Oracle uses materialized view logs
- SQL Server has indexed views with restrictions
- Postgres extensions like pg_ivm take a similar approach

One thing we should consider is whether to:
a) Modify the executor to track changes during DML
b) Use triggers to capture changes
c) Use logical decoding

Each has tradeoffs. Triggers are simpler but have overhead.
Executor changes are more invasive but more efficient.

I'd vote for starting with (b) for the initial implementation.

--
Andres Freund""",
        "thread_id": "incremental-matview-01",
    },
    {
        "id": "CAK48Jm_Xx2vL9mN@mail.gmail.com",
        "message_id": "<CAK48Jm_Xx2vL9mN@mail.gmail.com>",
        "subject": "PATCH: Improve hash join performance for skewed data",
        "author": "David Rowley <dgrowley@gmail.com>",
        "date": "2024-12-14 09:15:22",
        "content": """Hi all,

Attached is a patch that improves hash join performance when the build side
has skewed data (many duplicate keys).

The problem:
When building a hash table with many duplicate keys, we can end up with
very long hash chains. This makes probing O(n) instead of O(1).

The solution:
This patch implements a hybrid approach:
1. For buckets with >100 entries, we build a secondary index
2. We use a simple bitmap to quickly check for non-existent keys
3. Added statistics collection to detect skew during planning

Benchmarks on TPC-H Query 9 with skewed data:
- Before: 45.2 seconds
- After: 12.8 seconds (3.5x improvement)

Please review and provide feedback.

--
David Rowley
PostgreSQL Contributor""",
        "thread_id": "hash-join-skew-01",
    },
    {
        "id": "87zfq8kj2m.fsf@postgresql.org",
        "message_id": "<87zfq8kj2m.fsf@postgresql.org>",
        "subject": "Re: PATCH: Improve hash join performance for skewed data",
        "author": "Robert Haas <robertmhaas@gmail.com>",
        "date": "2024-12-14 11:42:18",
        "content": """On Sat, Dec 14, 2024 at 9:15 AM David Rowley wrote:
> Attached is a patch that improves hash join performance when the build side
> has skewed data (many duplicate keys).

This looks promising. A few comments on the code:

1. In hashjoin.c line 234, I think we need to handle the case where
   the secondary index allocation fails. Currently we'd crash.

2. The threshold of 100 entries seems arbitrary. Should this be
   configurable via GUC? Or maybe calculated based on bucket size?

3. The bitmap approach is clever, but I'm worried about memory usage
   for very large tables. Have you measured the overhead?

4. Please add some regression tests covering the skewed data case.

Overall I think this is a good direction. With the above addressed,
I'd be +1 on committing this for v18.

--
Robert Haas
EDB: http://www.enterprisedb.com""",
        "thread_id": "hash-join-skew-01",
    },
    {
        "id": "CAAKRu_YxQ7-abc123@mail.gmail.com",
        "message_id": "<CAAKRu_YxQ7-abc123@mail.gmail.com>",
        "subject": "RFC: JSON path improvements for v18",
        "author": "Alvaro Herrera <alvherre@alvh.no-ip.org>",
        "date": "2024-12-13 16:20:00",
        "content": """Hi,

I'd like to propose some improvements to our JSON path implementation
for the upcoming v18 release.

Current limitations:
1. No support for recursive descent (..)
2. Limited filter expressions
3. No array slicing [start:end]

Proposed additions:
1. Recursive descent operator
   SELECT jsonb_path_query(data, '$..name')
   Would find all 'name' keys at any level

2. Enhanced filters with regex support
   SELECT jsonb_path_query(data, '$.items[?(@.name like_regex "^test")]')

3. Array slicing
   SELECT jsonb_path_query(data, '$.items[2:5]')

These would bring us closer to JSONPath spec compliance and match
what users expect coming from other databases or jq.

Implementation plan:
- Phase 1: Recursive descent (2 weeks)
- Phase 2: Array slicing (1 week)
- Phase 3: Enhanced filters (3 weeks)

I'll start working on this if there's interest.

--
Álvaro Herrera""",
        "thread_id": "jsonpath-v18-01",
    },
    {
        "id": "20241212.142233.98765@postgresql.org",
        "message_id": "<20241212.142233.98765@postgresql.org>",
        "subject": "Performance regression in parallel query after commit abc123",
        "author": "Amit Kapila <amit.kapila16@gmail.com>",
        "date": "2024-12-12 14:22:33",
        "content": """Hi,

I've noticed a performance regression in parallel query execution after
commit abc123def456 ("Refactor worker communication").

Test case:
  CREATE TABLE large_test AS SELECT generate_series(1,100000000) i;
  SET max_parallel_workers_per_gather = 4;
  SELECT count(*) FROM large_test WHERE i % 1000 = 0;

Before: 8.5 seconds
After: 14.2 seconds (67% slower)

I've bisected this to the commit mentioned above. Looking at the code,
I think the issue is in the new message passing logic - we're now
serializing/deserializing messages even when not necessary.

Quick fix attached. Please review.

--
Amit Kapila
PostgreSQL Contributor""",
        "thread_id": "parallel-regression-01",
    },
    {
        "id": "ZnKp2_message789@postgresql.org",
        "message_id": "<ZnKp2_message789@postgresql.org>",
        "subject": "Re: Performance regression in parallel query after commit abc123",
        "author": "Thomas Munro <thomas.munro@gmail.com>",
        "date": "2024-12-12 16:45:00",
        "content": """On Thu, Dec 12, 2024 at 2:22 PM Amit Kapila wrote:
> I've noticed a performance regression in parallel query execution

Oops, that's my fault. The refactoring was meant to simplify the code
but I didn't realize the performance impact.

Your fix looks correct. I've also added a micro-optimization to batch
small messages together, which should help even more.

Updated patch attached. With this:
- Your test case: 7.8 seconds (8% faster than original!)
- TPC-H Q1 parallel: 5% improvement
- TPC-H Q6 parallel: 3% improvement

Thanks for catching this before release.

--
Thomas Munro""",
        "thread_id": "parallel-regression-01",
    },
    {
        "id": "CAGRrpzY-planning123@mail.gmail.com",
        "message_id": "<CAGRrpzY-planning123@mail.gmail.com>",
        "subject": "Commitfest 2024-12 status update",
        "author": "Michael Paquier <michael@paquier.xyz>",
        "date": "2024-12-10 08:00:00",
        "content": """Hi all,

Here's the status update for the December 2024 commitfest:

Total patches: 142
- Committed: 45
- Ready for Committer: 23
- Needs Review: 52
- Waiting on Author: 18
- Withdrawn: 4

Notable commits this week:
1. Incremental backup improvements (Fujii Masao)
2. New pg_stat_io views (Melanie Plageman)
3. Parallel CREATE INDEX for BRIN (Matthias van de Meent)

Patches needing review (please help!):
- "Improve ANALYZE statistics for arrays" - no reviews yet
- "Add pg_buffercache_usage_counts view" - one review, needs more
- "MERGE command improvements" - waiting for committer feedback

Let's try to clear the backlog before the holiday break.

--
Michael Paquier
PostgreSQL Committer""",
        "thread_id": "commitfest-status-202412",
    },
]


def init_database(db_path: str) -> duckdb.DuckDBPyConnection:
    """Initialize DuckDB database."""
    conn = duckdb.connect(db_path)

    # Create messages table
    conn.execute("""
        CREATE OR REPLACE TABLE messages (
            id VARCHAR PRIMARY KEY,
            message_id VARCHAR,
            subject VARCHAR,
            author VARCHAR,
            date TIMESTAMP,
            content TEXT,
            url VARCHAR,
            thread_id VARCHAR,
            list_name VARCHAR DEFAULT 'pgsql-hackers',
            crawled_at TIMESTAMP DEFAULT current_timestamp
        )
    """)

    return conn


def main():
    print("Creating DuckDB database with sample PostgreSQL mailing list data...")
    conn = init_database(DATABASE_PATH)

    # Insert sample messages
    for msg in SAMPLE_MESSAGES:
        conn.execute("""
            INSERT INTO messages (id, message_id, subject, author, date, content, thread_id, list_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            msg["id"],
            msg["message_id"],
            msg["subject"],
            msg["author"],
            msg["date"],
            msg["content"],
            msg["thread_id"],
            "pgsql-hackers"
        ])

    conn.commit()

    # Display results
    print(f"\nInserted {len(SAMPLE_MESSAGES)} messages")
    print("\n" + "=" * 100)
    print("SAMPLE DATA:")
    print("=" * 100)

    result = conn.execute("""
        SELECT
            id,
            subject,
            author,
            date,
            thread_id,
            length(content) as content_length
        FROM messages
        ORDER BY date DESC
    """).fetchall()

    columns = ['id', 'subject', 'author', 'date', 'thread_id', 'content_length']
    print(f"\n{' | '.join(columns)}")
    print("-" * 100)

    for row in result:
        print(f"{row[0][:30]:<30} | {row[1][:40]:<40} | {row[2][:25]:<25} | {row[3]} | {row[4]:<25} | {row[5]}")

    # Show some statistics
    print("\n" + "=" * 100)
    print("STATISTICS:")
    print("=" * 100)

    stats = conn.execute("""
        SELECT
            COUNT(*) as total_messages,
            COUNT(DISTINCT thread_id) as threads,
            COUNT(DISTINCT author) as unique_authors,
            AVG(length(content))::INTEGER as avg_content_length,
            MIN(date) as earliest,
            MAX(date) as latest
        FROM messages
    """).fetchone()

    print(f"Total messages: {stats[0]}")
    print(f"Unique threads: {stats[1]}")
    print(f"Unique authors: {stats[2]}")
    print(f"Avg content length: {stats[3]} chars")
    print(f"Date range: {stats[4]} to {stats[5]}")

    # Show a full message example
    print("\n" + "=" * 100)
    print("FULL MESSAGE EXAMPLE:")
    print("=" * 100)

    full_msg = conn.execute("""
        SELECT subject, author, date, content
        FROM messages
        LIMIT 1
    """).fetchone()

    print(f"Subject: {full_msg[0]}")
    print(f"From: {full_msg[1]}")
    print(f"Date: {full_msg[2]}")
    print(f"\nContent:\n{full_msg[3][:500]}...")

    conn.close()
    print(f"\n\nDatabase saved to: {DATABASE_PATH}")


if __name__ == "__main__":
    main()
