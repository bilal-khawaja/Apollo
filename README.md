🏥 Multi-Tenant Hospital Inventory & Automated Ordering System

An enterprise-grade B2B healthcare inventory management platform designed to track specialized medical stock dynamically across complex physical infrastructure layouts for hospitals and clinics.
1. What the Project Is

The system bridges two core operational realities:

Dynamic Bulk Onboarding: Administrators can provision thousands of items, system locations, or catalog definitions using rapid spreadsheet uploads (.xlsx, .xls).
Real-Time Clinical Operations: Frontline medical professionals (pharmacists, nurses) interact with the system via physical hardware barcode scanning, executing item-by-item state mutations (consumption or checkout).

Core Technical Stack

Backend Framework: FastAPI (Python)
ORM / Database Layer: SQLModel (built on SQLAlchemy & Pydantic v2)
Automation & Webhooks: n8n (handling file generation, external communications, and process workflows)
Concurrency & Caching: Redis (planned for Idempotency & Task management)


2. How It Handles Concurrency and Idempotency

Maintaining data consistency in a healthcare environment where multiple terminals or automated webhooks can fire simultaneously is critical.

Database-Level Protection: SQLModel/SQLAlchemy leverages strict transactional isolation levels. Multi-tenant partitioning ensures organization-level isolation, preventing cross-tenant data leaks or race conditions during high-volume stock adjustments.
Idempotency Strategy via Redis: To prevent duplicate order placements or double-processing of webhook events (e.g., if n8n retries a failed notification request), the backend uses Redis-backed idempotency keys. Incoming requests carry unique transaction IDs; Redis checks and locks these keys transiently to ensure operations are processed exactly once.

3. How Inputs and Outputs Are Handled (and Why via Excel Sheets)

Medical inventory data exists in massive abundance, often originating from legacy supplier catalogs, bulk audits, or external hospital reporting structures.

Bulk Inputs: Rather than forcing slow, single-item UI entries for massive inventories, the system uses an intelligent multi-track endpoint (/add_products). It handles bulk spreadsheet uploads (.xlsx), gathers row identifiers in a single batch using SQL's .in_() clause, constructs lightning-fast dictionary lookups (barcode_to_id_map), and executes all-at-once database commits.
Outputs & File Generation: Data exports and sheet creation are offloaded to streamline performance. While complex heavy computations happen via optimized backend structures, file creation and transformation duties are delegated to visual visual pipelines to keep database latency low.


4. Shifting Excel Features from Pandas to n8n

To optimize application boundaries, we are progressively migrating heavy data presentation and file operations away from internal Python code (`pandas`) into visual workflow automation via n8n:

Sheet Generation: Document compilation, formatting, and report output creation are now structurally handled inside n8n workflows.
Operational Separation: By moving formatting logic, template routing, and file generation outside of the core Python backend, we protect the primary database and API threads from performance bottlenecks caused by heavy file rendering loops.

5. Why We Chose n8n (Architectural Rationale)

I chose an event-driven webhook architecture with n8n for two main reasons: architectural decoupling and operational efficiency."
1. First, I wanted to keep the core FastAPI backend focused entirely on high-performance clinical transactions, like barcode scanning, where sub-second latency is critical. Running Celery introduces an 'infrastructure tax' you have to manage Redis brokers, monitor worker daemons, and handle task serialization schemas just to send notifications.
2. Second, business workflows like email styling, routing, and PDF creation change frequently. By offloading this to n8n, we completely decouple our business logic. If a hospital administrator wants to edit the PDF formatting of a purchase order or route low-stock alerts to Slack instead of email, we can build and test that visually in n8n in minutes without having to refactor code, run tests, or redeploy our core FastAPI application.


6. Automated Order Placement When Stocks Hit Low Levels

The system implements automated inventory monitoring to prevent critical healthcare stockouts:

Self-Policing Data Validation: The database enforces strict rules via Pydantic and SQLModel validators no negative numeric values are permitted on quantities, product strengths (p_mg), or transaction costs. Transactions enforce that total_cost must mathematically equal the sum of total_product_cost + delivery_charges + tax_amount down to a 2-decimal rounding precision.
Low-Stock Trigger & Workflow: When a barcode scan or consumption event drops an item's stock beneath its designated threshold, the backend emits a low-stock event payload.
n8n Automation Loop: n8n intercepts the webhook, formats the purchase order, generates external notifications or supplier emails, and tracks delivery status. If a supplier email fails (e.g., inbox full), administrators can inspect the failure instantly in the n8n UI, correct data, and trigger a manual retry without touching backend infrastructure.

