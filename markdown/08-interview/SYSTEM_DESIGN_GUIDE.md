# The Ultimate System Design Guide

A comprehensive framework for designing production-grade systems without compromises.

---

## Table of Contents

1. [Design Philosophy](#1-design-philosophy)
2. [The SACRED Framework](#2-the-sacred-framework)
3. [System Design Methodology](#3-system-design-methodology)
4. [Core Components Checklist](#4-core-components-checklist)
5. [Non-Functional Requirements](#5-non-functional-requirements)
6. [Industry Templates](#6-industry-templates)
   - [E-Commerce Platform](#61-e-commerce-platform)
   - [Social Media Platform](#62-social-media-platform)
   - [FinTech / Banking System](#63-fintech--banking-system)
   - [Healthcare System](#64-healthcare-system)
   - [Real-Time Streaming Platform](#65-real-time-streaming-platform)
   - [AI/ML Platform](#66-aiml-platform)
   - [SaaS Multi-Tenant Platform](#67-saas-multi-tenant-platform)
   - [IoT Platform](#68-iot-platform)
7. [Database Selection Guide](#7-database-selection-guide)
8. [API Design Principles](#8-api-design-principles)
9. [Security Architecture](#9-security-architecture)
10. [Observability Stack](#10-observability-stack)
11. [Interview Presentation Template](#11-interview-presentation-template)

---

## 1. Design Philosophy

### The Three Pillars of Excellent System Design

```
┌─────────────────────────────────────────────────────────────┐
│                    SYSTEM EXCELLENCE                         │
├─────────────────┬─────────────────┬─────────────────────────┤
│   RELIABILITY   │   SCALABILITY   │      MAINTAINABILITY    │
│                 │                 │                         │
│ • Works when    │ • Handles load  │ • Easy to understand    │
│   needed        │   growth        │ • Easy to modify        │
│ • Handles       │ • Cost grows    │ • Easy to operate       │
│   failures      │   linearly      │ • Easy to debug         │
│ • Data intact   │ • No redesign   │ • Easy to extend        │
└─────────────────┴─────────────────┴─────────────────────────┘
```

### Design Principles to Never Compromise

| Principle | Description | Never Skip Because... |
|-----------|-------------|----------------------|
| **Single Responsibility** | Each component does one thing well | Debugging becomes impossible otherwise |
| **Loose Coupling** | Components communicate via contracts | Change one thing, break everything otherwise |
| **High Cohesion** | Related logic stays together | Code becomes scattered spaghetti otherwise |
| **Defense in Depth** | Multiple layers of protection | One breach shouldn't compromise everything |
| **Graceful Degradation** | Partial functionality > total failure | Users need something, not nothing |
| **Observability First** | If you can't measure it, you can't manage it | Flying blind in production is dangerous |
| **Idempotency** | Same operation, same result | Retries cause chaos otherwise |
| **Immutability Where Possible** | Data that doesn't change is data that can't corrupt | Simplifies reasoning about state |

---

## 2. The SACRED Framework

Use this acronym to ensure you cover all critical aspects:

### **S** - Scalability
```
Questions to Answer:
├── How many users? (Current vs 10x vs 100x)
├── How much data? (Current vs growth rate)
├── Read:Write ratio?
├── Peak vs average load?
├── Geographic distribution?
└── Scaling strategy: Vertical → Horizontal → Distributed
```

### **A** - Availability
```
Questions to Answer:
├── Required uptime? (99.9% = 8.76 hours downtime/year)
├── Single points of failure?
├── Failover strategy?
├── Data replication strategy?
├── Disaster recovery plan?
└── Graceful degradation options?
```

### **C** - Consistency
```
Questions to Answer:
├── Strong vs eventual consistency?
├── Which operations MUST be consistent?
├── CAP theorem trade-offs?
├── Conflict resolution strategy?
├── Transaction boundaries?
└── Idempotency requirements?
```

### **R** - Reliability
```
Questions to Answer:
├── Failure modes and handling?
├── Data durability guarantees?
├── Backup and recovery strategy?
├── Circuit breaker patterns?
├── Retry policies?
└── Chaos engineering approach?
```

### **E** - Efficiency
```
Questions to Answer:
├── Latency requirements (p50, p95, p99)?
├── Throughput requirements?
├── Resource utilization targets?
├── Cost optimization strategy?
├── Caching strategy?
└── Query optimization approach?
```

### **D** - Developability
```
Questions to Answer:
├── Team structure and ownership?
├── Deployment frequency?
├── Testing strategy?
├── Documentation approach?
├── Onboarding new developers?
└── Technical debt management?
```

---

## 3. System Design Methodology

### Phase 1: Requirements Gathering (5 minutes in interview)

```
┌─────────────────────────────────────────────────────────────┐
│                  REQUIREMENTS CHECKLIST                      │
├─────────────────────────────────────────────────────────────┤
│ FUNCTIONAL                                                   │
│ □ Core features (what must the system do?)                  │
│ □ User types and roles                                      │
│ □ Critical user journeys                                    │
│ □ Data inputs and outputs                                   │
│ □ Integration points                                        │
├─────────────────────────────────────────────────────────────┤
│ NON-FUNCTIONAL                                              │
│ □ Scale: Users, requests/sec, data volume                   │
│ □ Latency: p50, p95, p99 targets                           │
│ □ Availability: SLA percentage                              │
│ □ Consistency: Strong vs eventual                           │
│ □ Security: Compliance, data sensitivity                    │
│ □ Geography: Single region vs multi-region                  │
├─────────────────────────────────────────────────────────────┤
│ CONSTRAINTS                                                  │
│ □ Budget                                                    │
│ □ Timeline                                                  │
│ □ Team size and expertise                                   │
│ □ Existing infrastructure                                   │
│ □ Regulatory requirements                                   │
└─────────────────────────────────────────────────────────────┘
```

### Phase 2: High-Level Design (10 minutes in interview)

```
Step 1: Identify Core Components
         ↓
Step 2: Define Data Flow
         ↓
Step 3: Choose Communication Patterns
         ↓
Step 4: Select Storage Solutions
         ↓
Step 5: Design API Contracts
```

### Phase 3: Deep Dive (15 minutes in interview)

```
Pick 2-3 critical components and detail:
├── Data model
├── Algorithm/Logic
├── Failure handling
├── Scaling approach
└── Trade-offs made
```

### Phase 4: Address Bottlenecks (5 minutes in interview)

```
Identify and solve:
├── Single points of failure
├── Performance bottlenecks
├── Security vulnerabilities
├── Operational concerns
└── Cost drivers
```

---

## 4. Core Components Checklist

### Every Production System Needs:

```
┌─────────────────────────────────────────────────────────────┐
│                    CORE COMPONENTS                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   CLIENTS   │───▶│ LOAD BALANCER│───▶│  API GATEWAY │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│                                               │              │
│                     ┌─────────────────────────┼──────────┐   │
│                     ▼                         ▼          ▼   │
│              ┌───────────┐           ┌───────────┐ ┌──────┐ │
│              │  SERVICE  │           │  SERVICE  │ │ AUTH │ │
│              │    A      │           │    B      │ │      │ │
│              └───────────┘           └───────────┘ └──────┘ │
│                     │                         │              │
│         ┌──────────┴──────────┐    ┌─────────┴─────────┐   │
│         ▼                     ▼    ▼                   ▼   │
│  ┌───────────┐         ┌───────────┐           ┌───────────┐│
│  │   CACHE   │         │ DATABASE  │           │   QUEUE   ││
│  │  (Redis)  │         │(Primary)  │           │ (Kafka)   ││
│  └───────────┘         └───────────┘           └───────────┘│
│                              │                       │      │
│                              ▼                       ▼      │
│                       ┌───────────┐          ┌───────────┐  │
│                       │  REPLICA  │          │  WORKERS  │  │
│                       │ DATABASE  │          │           │  │
│                       └───────────┘          └───────────┘  │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│                    OBSERVABILITY LAYER                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │  LOGS    │  │ METRICS  │  │ TRACES   │  │ ALERTS   │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Component Selection Matrix

| Component | Options | When to Use |
|-----------|---------|-------------|
| **Load Balancer** | AWS ALB, Nginx, HAProxy | Always for >1 server |
| **API Gateway** | Kong, AWS API Gateway, Envoy | Auth, rate limiting, routing |
| **Service Mesh** | Istio, Linkerd | Microservices communication |
| **Cache** | Redis, Memcached | Read-heavy, computed data |
| **Message Queue** | Kafka, RabbitMQ, SQS | Async processing, decoupling |
| **Search** | Elasticsearch, Algolia | Full-text search, analytics |
| **CDN** | CloudFront, Cloudflare | Static assets, global users |
| **Object Storage** | S3, GCS, MinIO | Files, images, backups |

---

## 5. Non-Functional Requirements

### Latency Targets by System Type

| System Type | p50 | p95 | p99 |
|-------------|-----|-----|-----|
| E-commerce checkout | <200ms | <500ms | <1s |
| Social feed | <100ms | <300ms | <500ms |
| Search | <50ms | <200ms | <500ms |
| Real-time gaming | <50ms | <100ms | <150ms |
| Banking transaction | <500ms | <1s | <2s |
| Analytics dashboard | <2s | <5s | <10s |
| Batch processing | N/A | N/A | <hours |

### Availability Targets

| Level | Uptime | Downtime/Year | Downtime/Month | Use Case |
|-------|--------|---------------|----------------|----------|
| 99% | "Two nines" | 3.65 days | 7.3 hours | Internal tools |
| 99.9% | "Three nines" | 8.76 hours | 43.8 min | Business apps |
| 99.95% | | 4.38 hours | 21.9 min | E-commerce |
| 99.99% | "Four nines" | 52.6 min | 4.38 min | Financial systems |
| 99.999% | "Five nines" | 5.26 min | 26.3 sec | Critical infrastructure |

### Scalability Calculations

```
Daily Active Users (DAU): 10 million
Average actions per user per day: 20
Total daily requests: 200 million
Requests per second (average): 200M / 86400 ≈ 2,300 RPS
Peak (3x average): ~7,000 RPS
Design for (2x peak): ~15,000 RPS

Storage calculation:
- 10M users × 1KB profile = 10GB
- 200M actions × 100 bytes = 20GB/day
- 1 year retention: 7.3TB
- Design for: 20TB with replication
```

---

## 6. Industry Templates

---

### 6.1 E-Commerce Platform

```
┌─────────────────────────────────────────────────────────────────┐
│                    E-COMMERCE ARCHITECTURE                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────┐     ┌─────────────────────────────────────────┐   │
│   │   CDN   │────▶│              WEB/MOBILE                 │   │
│   │(Static) │     │              CLIENTS                    │   │
│   └─────────┘     └─────────────────────────────────────────┘   │
│                                    │                             │
│                                    ▼                             │
│                          ┌─────────────────┐                    │
│                          │   API GATEWAY   │                    │
│                          │ • Auth          │                    │
│                          │ • Rate Limit    │                    │
│                          │ • SSL Term      │                    │
│                          └─────────────────┘                    │
│                                    │                             │
│         ┌──────────────────────────┼──────────────────────┐     │
│         ▼                          ▼                      ▼     │
│  ┌─────────────┐          ┌─────────────┐        ┌───────────┐ │
│  │   PRODUCT   │          │    ORDER    │        │   USER    │ │
│  │   SERVICE   │          │   SERVICE   │        │  SERVICE  │ │
│  └─────────────┘          └─────────────┘        └───────────┘ │
│         │                          │                      │     │
│         ▼                          ▼                      ▼     │
│  ┌─────────────┐          ┌─────────────┐        ┌───────────┐ │
│  │  CATALOG DB │          │  ORDER DB   │        │  USER DB  │ │
│  │ (PostgreSQL)│          │ (PostgreSQL)│        │(PostgreSQL)│ │
│  └─────────────┘          └─────────────┘        └───────────┘ │
│         │                          │                             │
│         │    ┌─────────────────────┤                            │
│         ▼    ▼                     ▼                            │
│  ┌─────────────────┐      ┌─────────────────┐                   │
│  │ ELASTICSEARCH   │      │   MESSAGE QUEUE │                   │
│  │ (Product Search)│      │    (Kafka)      │                   │
│  └─────────────────┘      └─────────────────┘                   │
│                                    │                             │
│                    ┌───────────────┼───────────────┐            │
│                    ▼               ▼               ▼            │
│            ┌───────────┐   ┌───────────┐   ┌───────────┐       │
│            │ INVENTORY │   │  PAYMENT  │   │NOTIFICATION│       │
│            │  WORKER   │   │  WORKER   │   │  WORKER   │       │
│            └───────────┘   └───────────┘   └───────────┘       │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  REDIS CLUSTER                                          │   │
│  │  • Session store   • Cart cache   • Inventory cache    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Key Design Points

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| **Product Catalog** | PostgreSQL + Elasticsearch | ACID for inventory, fast search |
| **Shopping Cart** | Redis with persistence | Fast access, session-based |
| **Order Processing** | Event-driven (Kafka) | Decouple payment, inventory, notification |
| **Inventory** | Write-ahead log pattern | Prevent overselling |
| **Payment** | Saga pattern with compensation | Handle partial failures |
| **Search** | Elasticsearch with Redis cache | Sub-100ms search results |

#### Critical Flows

**Checkout Flow (Must be reliable):**
```
1. Validate cart items in stock
2. Reserve inventory (soft lock)
3. Process payment (external)
4. If payment success:
   - Confirm inventory deduction
   - Create order record
   - Trigger notifications
5. If payment fails:
   - Release inventory reservation
   - Return error to user
```

---

### 6.2 Social Media Platform

```
┌─────────────────────────────────────────────────────────────────┐
│                   SOCIAL MEDIA ARCHITECTURE                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │                    MOBILE / WEB CLIENTS                  │   │
│   └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│              ┌───────────────┼───────────────┐                  │
│              ▼               ▼               ▼                  │
│      ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│      │  WebSocket  │ │    REST     │ │   GraphQL   │           │
│      │   Gateway   │ │   Gateway   │ │   Gateway   │           │
│      │  (Real-time)│ │   (CRUD)    │ │  (Queries)  │           │
│      └─────────────┘ └─────────────┘ └─────────────┘           │
│              │               │               │                   │
│              └───────────────┼───────────────┘                  │
│                              ▼                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                     SERVICE MESH                          │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │  │
│  │  │  USER   │ │  POST   │ │  FEED   │ │ SOCIAL  │        │  │
│  │  │ SERVICE │ │ SERVICE │ │ SERVICE │ │ GRAPH   │        │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘        │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │  │
│  │  │  MEDIA  │ │ SEARCH  │ │NOTIFIC- │ │ CHAT    │        │  │
│  │  │ SERVICE │ │ SERVICE │ │ ATION   │ │ SERVICE │        │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘        │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│         ┌────────────────────┼────────────────────┐             │
│         ▼                    ▼                    ▼             │
│  ┌─────────────┐     ┌─────────────┐      ┌─────────────┐      │
│  │  CASSANDRA  │     │   NEO4J     │      │  REDIS      │      │
│  │  (Posts,    │     │  (Social    │      │  (Feed      │      │
│  │   Timelines)│     │   Graph)    │      │   Cache)    │      │
│  └─────────────┘     └─────────────┘      └─────────────┘      │
│         │                                                        │
│         ▼                                                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    KAFKA CLUSTER                         │   │
│  │  • Post events  • Likes  • Comments  • Follows          │   │
│  └─────────────────────────────────────────────────────────┘   │
│         │                                                        │
│         ▼                                                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    STREAM PROCESSORS                     │   │
│  │  • Feed Builder  • Trending Calculator  • ML Ranking    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Key Design Points

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| **Feed Generation** | Fan-out on write (hybrid) | Pre-compute for most users, on-read for celebrities |
| **Social Graph** | Neo4j (graph DB) | Friend recommendations, degrees of separation |
| **Posts Storage** | Cassandra | High write throughput, eventual consistency OK |
| **Real-time** | WebSocket + Redis Pub/Sub | Live notifications, typing indicators |
| **Media** | S3 + CDN + transcoding pipeline | Multiple resolutions, global delivery |
| **Search** | Elasticsearch + ML ranking | Relevance, personalization |

#### Feed Generation Strategy

```
HYBRID FAN-OUT APPROACH:

For Regular Users (< 1000 followers):
├── User posts → Write to followers' feed caches
├── Fan-out on WRITE
└── O(followers) write operations

For Celebrities (> 10000 followers):
├── User posts → Write to own timeline only
├── Followers PULL on read
├── Fan-out on READ
└── Avoids millions of writes

Merge at Read Time:
├── Get cached feed
├── Fetch celebrity posts
├── Merge and rank
└── Return top N
```

---

### 6.3 FinTech / Banking System

```
┌─────────────────────────────────────────────────────────────────┐
│                    BANKING SYSTEM ARCHITECTURE                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                SECURITY PERIMETER                        │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐    │   │
│  │  │   WAF   │  │   DDoS  │  │   IDS/  │  │   API   │    │   │
│  │  │         │  │ Protect │  │   IPS   │  │ Gateway │    │   │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              AUTHENTICATION & AUTHORIZATION              │   │
│  │  • MFA   • Biometrics   • OAuth 2.0   • mTLS           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│         ┌────────────────────┼────────────────────┐             │
│         ▼                    ▼                    ▼             │
│  ┌─────────────┐     ┌─────────────┐      ┌─────────────┐      │
│  │   ACCOUNT   │     │ TRANSACTION │      │   PAYMENT   │      │
│  │   SERVICE   │     │   SERVICE   │      │   SERVICE   │      │
│  │             │     │             │      │             │      │
│  │ • Balance   │     │ • Transfer  │      │ • Bill Pay  │      │
│  │ • History   │     │ • Validate  │      │ • External  │      │
│  │ • Limits    │     │ • Execute   │      │ • SWIFT     │      │
│  └─────────────┘     └─────────────┘      └─────────────┘      │
│         │                    │                    │             │
│         │           ┌───────┴───────┐            │             │
│         │           ▼               ▼            │             │
│         │    ┌───────────┐   ┌───────────┐      │             │
│         │    │   FRAUD   │   │    AML    │      │             │
│         │    │ DETECTION │   │ SCREENING │      │             │
│         │    │   (ML)    │   │           │      │             │
│         │    └───────────┘   └───────────┘      │             │
│         │           │               │            │             │
│         ▼           ▼               ▼            ▼             │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   CORE BANKING DATABASE                  │   │
│  │     PostgreSQL (Primary) + Synchronous Replication      │   │
│  │                                                          │   │
│  │  • SERIALIZABLE isolation level                         │   │
│  │  • Point-in-time recovery                               │   │
│  │  • Encrypted at rest (AES-256)                          │   │
│  │  • Full audit logging                                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    AUDIT & COMPLIANCE                    │   │
│  │  • Immutable audit log  • SOX compliance  • PCI-DSS    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Key Design Points

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| **Transactions** | SERIALIZABLE isolation | Money transfers MUST be atomic |
| **Replication** | Synchronous (not async) | Zero data loss tolerance |
| **Audit** | Append-only, immutable logs | Regulatory requirement |
| **Fraud Detection** | Real-time ML scoring | Block suspicious transactions |
| **Encryption** | End-to-end, at rest, in transit | PCI-DSS compliance |
| **Availability** | Active-active multi-region | 99.99% uptime requirement |

#### Money Transfer Pattern (ACID Critical)

```
BEGIN TRANSACTION (SERIALIZABLE)
│
├── 1. Lock source account
├── 2. Verify balance >= amount
├── 3. Lock destination account
├── 4. Debit source account
├── 5. Credit destination account
├── 6. Create transaction record
├── 7. Create audit log entry
│
COMMIT TRANSACTION
│
├── If success: Trigger notifications
└── If failure: Automatic rollback, no partial state
```

---

### 6.4 Healthcare System

```
┌─────────────────────────────────────────────────────────────────┐
│                   HEALTHCARE SYSTEM ARCHITECTURE                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  HIPAA COMPLIANCE LAYER                  │   │
│  │  • PHI Encryption  • Access Logging  • Data Masking    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│         ┌────────────────────┼────────────────────┐             │
│         ▼                    ▼                    ▼             │
│  ┌─────────────┐     ┌─────────────┐      ┌─────────────┐      │
│  │  PATIENT    │     │   CLINICAL  │      │   BILLING   │      │
│  │  PORTAL     │     │    PORTAL   │      │   SYSTEM    │      │
│  │             │     │             │      │             │      │
│  │ • Records   │     │ • EHR       │      │ • Claims    │      │
│  │ • Appts     │     │ • Orders    │      │ • Insurance │      │
│  │ • Messages  │     │ • Results   │      │ • Payments  │      │
│  └─────────────┘     └─────────────┘      └─────────────┘      │
│         │                    │                    │             │
│         └────────────────────┼────────────────────┘             │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    FHIR API GATEWAY                      │   │
│  │  (HL7 FHIR R4 Standard Compliance)                      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│         ┌────────────────────┼────────────────────┐             │
│         ▼                    ▼                    ▼             │
│  ┌─────────────┐     ┌─────────────┐      ┌─────────────┐      │
│  │   PATIENT   │     │  CLINICAL   │      │   IMAGING   │      │
│  │   SERVICE   │     │   SERVICE   │      │   SERVICE   │      │
│  └─────────────┘     └─────────────┘      └─────────────┘      │
│         │                    │                    │             │
│         ▼                    ▼                    ▼             │
│  ┌─────────────┐     ┌─────────────┐      ┌─────────────┐      │
│  │  PATIENT    │     │    EHR      │      │    PACS     │      │
│  │  DATABASE   │     │  DATABASE   │      │  (DICOM)    │      │
│  │ (Encrypted) │     │ (Encrypted) │      │             │      │
│  └─────────────┘     └─────────────┘      └─────────────┘      │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              INTEROPERABILITY LAYER                      │   │
│  │  • HL7 v2 Interface  • FHIR APIs  • CCD/CDA Exchange   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    ANALYTICS PLATFORM                    │   │
│  │  • Population Health  • Clinical Decision Support       │   │
│  │  • De-identified Data Warehouse                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Key Design Points

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| **Data Standard** | HL7 FHIR R4 | Industry standard, interoperability |
| **PHI Storage** | Encrypted PostgreSQL | HIPAA requirement |
| **Access Control** | RBAC + ABAC | Role + context-based (emergency access) |
| **Audit** | Immutable, 7-year retention | HIPAA audit requirements |
| **Imaging** | DICOM/PACS integration | Medical imaging standard |
| **Analytics** | De-identified data lake | Research without exposing PHI |

---

### 6.5 Real-Time Streaming Platform

```
┌─────────────────────────────────────────────────────────────────┐
│                 STREAMING PLATFORM ARCHITECTURE                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                      CONTENT INGESTION                    │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐    │   │
│  │  │ Upload  │  │  Live   │  │ Screen  │  │External │    │   │
│  │  │  VOD    │  │ Stream  │  │ Record  │  │  Feed   │    │   │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   TRANSCODING PIPELINE                   │   │
│  │                                                          │   │
│  │  Input → Decode → Scale → Encode → Package → Store      │   │
│  │                                                          │   │
│  │  Outputs: 360p, 480p, 720p, 1080p, 4K                   │   │
│  │  Formats: HLS, DASH, CMAF                                │   │
│  │  Codecs: H.264, H.265, VP9, AV1                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    CONTENT STORAGE                       │   │
│  │                                                          │   │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐ │   │
│  │  │   Origin    │    │  Hot Cache  │    │    CDN      │ │   │
│  │  │   (S3)      │───▶│  (Regional) │───▶│  (Global)   │ │   │
│  │  │             │    │             │    │  CloudFront │ │   │
│  │  └─────────────┘    └─────────────┘    └─────────────┘ │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    PLAYBACK LAYER                        │   │
│  │                                                          │   │
│  │  • Adaptive Bitrate (ABR) selection                     │   │
│  │  • DRM (Widevine, FairPlay, PlayReady)                  │   │
│  │  • Analytics beaconing                                   │   │
│  │  • Ad insertion (SSAI/CSAI)                             │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                REAL-TIME ANALYTICS                       │   │
│  │                                                          │   │
│  │  ┌─────────┐    ┌─────────┐    ┌─────────┐             │   │
│  │  │  Kafka  │───▶│  Flink  │───▶│ClickHse│             │   │
│  │  │ (Events)│    │(Process)│    │(Analytics)            │   │
│  │  └─────────┘    └─────────┘    └─────────┘             │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Key Design Points

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| **Delivery** | HLS + DASH | Universal device support |
| **CDN** | Multi-CDN with failover | 99.99% availability globally |
| **Encoding** | Per-title encoding | Optimize quality per content type |
| **Live Latency** | LL-HLS/LL-DASH (<3s) | Near real-time for sports |
| **DRM** | Multi-DRM (3 providers) | All device ecosystems |
| **Analytics** | Real-time + batch | QoE monitoring, recommendations |

---

### 6.6 AI/ML Platform

```
┌─────────────────────────────────────────────────────────────────┐
│                    AI/ML PLATFORM ARCHITECTURE                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    DATA LAYER                            │   │
│  │                                                          │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐    │   │
│  │  │Raw Data │  │Feature  │  │ Model   │  │Inference│    │   │
│  │  │  Lake   │  │  Store  │  │Registry │  │  Cache  │    │   │
│  │  │  (S3)   │  │ (Feast) │  │(MLflow) │  │ (Redis) │    │   │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  TRAINING PIPELINE                       │   │
│  │                                                          │   │
│  │  Data Prep → Feature Eng → Training → Evaluation        │   │
│  │      │            │            │            │            │   │
│  │      ▼            ▼            ▼            ▼            │   │
│  │  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐        │   │
│  │  │ Spark  │  │  dbt   │  │PyTorch │  │ Great  │        │   │
│  │  │        │  │        │  │/TF/JAX │  │Expecta-│        │   │
│  │  │        │  │        │  │  +GPU  │  │ tions  │        │   │
│  │  └────────┘  └────────┘  └────────┘  └────────┘        │   │
│  │                                                          │   │
│  │  Orchestration: Airflow / Kubeflow Pipelines            │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  SERVING LAYER                           │   │
│  │                                                          │   │
│  │  ┌──────────────────────────────────────────────────┐   │   │
│  │  │              MODEL SERVING                        │   │   │
│  │  │                                                   │   │   │
│  │  │  ┌─────────┐  ┌─────────┐  ┌─────────┐          │   │   │
│  │  │  │  Batch  │  │Real-time│  │ Streaming│          │   │   │
│  │  │  │ (Spark) │  │(Triton) │  │ (Flink)  │          │   │   │
│  │  │  └─────────┘  └─────────┘  └─────────┘          │   │   │
│  │  └──────────────────────────────────────────────────┘   │   │
│  │                                                          │   │
│  │  • A/B Testing (model versions)                         │   │
│  │  • Shadow mode (new models)                             │   │
│  │  • Canary deployments                                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  MONITORING & FEEDBACK                   │   │
│  │                                                          │   │
│  │  • Model drift detection                                │   │
│  │  • Data quality monitoring                              │   │
│  │  • Prediction logging                                   │   │
│  │  • Human feedback loop                                  │   │
│  │  • Automated retraining triggers                        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Key Design Points

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| **Feature Store** | Feast | Consistency between training and serving |
| **Model Registry** | MLflow | Version control, lineage tracking |
| **Training** | Kubernetes + GPU nodes | Scale training jobs elastically |
| **Serving** | Triton Inference Server | Multi-framework, batching, GPU |
| **Monitoring** | Evidently + custom metrics | Drift detection, quality alerts |
| **Feedback** | Human-in-the-loop | Continuous improvement |

---

### 6.7 SaaS Multi-Tenant Platform

```
┌─────────────────────────────────────────────────────────────────┐
│                   MULTI-TENANT SAAS ARCHITECTURE                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    TENANT ROUTING                        │   │
│  │                                                          │   │
│  │  Request → Domain/Header → Tenant ID → Route            │   │
│  │                                                          │   │
│  │  tenant1.app.com  ─┐                                    │   │
│  │  tenant2.app.com  ─┼──▶  Tenant Resolution  ──▶  API    │   │
│  │  X-Tenant-ID      ─┘                                    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                 APPLICATION LAYER                        │   │
│  │                                                          │   │
│  │  ┌─────────────────────────────────────────────────┐    │   │
│  │  │           TENANT CONTEXT MIDDLEWARE              │    │   │
│  │  │  • Inject tenant_id into all queries            │    │   │
│  │  │  • Enforce row-level security                   │    │   │
│  │  │  • Apply tenant-specific configuration          │    │   │
│  │  └─────────────────────────────────────────────────┘    │   │
│  │                                                          │   │
│  │  Services: Auth, Core, Billing, Analytics               │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    DATA ISOLATION                        │   │
│  │                                                          │   │
│  │  OPTION A: Shared Database, Shared Schema               │   │
│  │  ┌─────────────────────────────────────────────────┐    │   │
│  │  │  users (tenant_id, user_id, ...)                │    │   │
│  │  │  orders (tenant_id, order_id, ...)              │    │   │
│  │  │  + Row-Level Security policies                  │    │   │
│  │  └─────────────────────────────────────────────────┘    │   │
│  │                                                          │   │
│  │  OPTION B: Shared Database, Separate Schemas            │   │
│  │  ┌─────────────────────────────────────────────────┐    │   │
│  │  │  tenant_001.users, tenant_001.orders            │    │   │
│  │  │  tenant_002.users, tenant_002.orders            │    │   │
│  │  └─────────────────────────────────────────────────┘    │   │
│  │                                                          │   │
│  │  OPTION C: Separate Databases (Enterprise tier)         │   │
│  │  ┌─────────────────────────────────────────────────┐    │   │
│  │  │  db_tenant_001, db_tenant_002 (isolated)        │    │   │
│  │  └─────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              BILLING & METERING                          │   │
│  │                                                          │   │
│  │  Usage Events → Aggregation → Invoice Generation        │   │
│  │                                                          │   │
│  │  Tiers: Free → Pro → Enterprise (custom pricing)        │   │
│  │  Limits: API calls, storage, users, features            │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Key Design Points

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| **Isolation Model** | Hybrid (shared + dedicated) | Cost efficiency + enterprise requirements |
| **Data Security** | Row-Level Security | Prevent cross-tenant data leakage |
| **Configuration** | Per-tenant feature flags | Customization without code changes |
| **Billing** | Usage-based metering | Fair pricing, revenue optimization |
| **Onboarding** | Automated provisioning | Self-service, instant activation |
| **Customization** | White-labeling support | Enterprise branding requirements |

---

### 6.8 IoT Platform

```
┌─────────────────────────────────────────────────────────────────┐
│                      IoT PLATFORM ARCHITECTURE                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    DEVICE LAYER                          │   │
│  │                                                          │   │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐           │   │
│  │  │Sensors │ │Actuator│ │Gateway │ │ Edge   │           │   │
│  │  │        │ │        │ │        │ │Compute │           │   │
│  │  └────────┘ └────────┘ └────────┘ └────────┘           │   │
│  │       │          │          │          │                │   │
│  │       └──────────┴──────────┴──────────┘                │   │
│  │                       │                                  │   │
│  │  Protocols: MQTT, CoAP, HTTP, LoRaWAN, Zigbee           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  CONNECTIVITY LAYER                      │   │
│  │                                                          │   │
│  │  ┌─────────────────────────────────────────────────┐    │   │
│  │  │              MQTT BROKER CLUSTER                 │    │   │
│  │  │  (EMQX / HiveMQ / Mosquitto)                    │    │   │
│  │  │                                                  │    │   │
│  │  │  • Device authentication (X.509, tokens)        │    │   │
│  │  │  • Topic-based routing                          │    │   │
│  │  │  • QoS levels (0, 1, 2)                         │    │   │
│  │  │  • Persistent sessions                          │    │   │
│  │  └─────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  PROCESSING LAYER                        │   │
│  │                                                          │   │
│  │  ┌─────────┐    ┌─────────┐    ┌─────────┐             │   │
│  │  │  Kafka  │───▶│  Flink  │───▶│  Rules  │             │   │
│  │  │(Ingest) │    │(Process)│    │ Engine  │             │   │
│  │  └─────────┘    └─────────┘    └─────────┘             │   │
│  │                      │              │                    │   │
│  │                      ▼              ▼                    │   │
│  │              ┌─────────────┐  ┌─────────────┐           │   │
│  │              │   Alerts    │  │   Actions   │           │   │
│  │              │(Thresholds) │  │(Actuators)  │           │   │
│  │              └─────────────┘  └─────────────┘           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    STORAGE LAYER                         │   │
│  │                                                          │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │   │
│  │  │  TimescaleDB │  │ InfluxDB   │  │    S3       │     │   │
│  │  │  (Time-series│  │(Metrics)   │  │ (Archive)   │     │   │
│  │  │   + SQL)     │  │            │  │             │     │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  APPLICATION LAYER                       │   │
│  │                                                          │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │   │
│  │  │Dashboard│ │ Mobile  │ │Analytics│ │   ML    │       │   │
│  │  │         │ │  App    │ │         │ │Predictive│      │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                 DEVICE MANAGEMENT                        │   │
│  │                                                          │   │
│  │  • Device registry (shadow/twin)                        │   │
│  │  • OTA firmware updates                                 │   │
│  │  • Remote configuration                                 │   │
│  │  • Fleet monitoring                                     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Key Design Points

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| **Protocol** | MQTT | Low bandwidth, pub/sub, QoS levels |
| **Time-Series DB** | TimescaleDB / InfluxDB | Optimized for time-stamped data |
| **Edge Computing** | Local processing | Reduce latency, bandwidth |
| **Device Twin** | Shadow state pattern | Handle offline devices |
| **Security** | X.509 certificates | Device authentication at scale |
| **OTA Updates** | Staged rollout | Safe firmware deployment |

---

## 7. Database Selection Guide

### Decision Matrix

```
┌─────────────────────────────────────────────────────────────────┐
│                  DATABASE SELECTION FLOWCHART                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Need ACID transactions?                                        │
│       │                                                          │
│       ├── YES ──▶ Need complex queries/joins?                   │
│       │               │                                          │
│       │               ├── YES ──▶ PostgreSQL / MySQL            │
│       │               │                                          │
│       │               └── NO ───▶ Need massive scale?           │
│       │                               │                          │
│       │                               ├── YES ──▶ CockroachDB   │
│       │                               └── NO ───▶ PostgreSQL    │
│       │                                                          │
│       └── NO ───▶ What's the primary access pattern?            │
│                       │                                          │
│                       ├── Key-Value ──▶ Redis / DynamoDB        │
│                       │                                          │
│                       ├── Document ───▶ MongoDB                 │
│                       │                                          │
│                       ├── Wide Column ──▶ Cassandra / ScyllaDB  │
│                       │                                          │
│                       ├── Graph ──────▶ Neo4j / Neptune         │
│                       │                                          │
│                       ├── Time-Series ──▶ TimescaleDB/InfluxDB  │
│                       │                                          │
│                       ├── Search ─────▶ Elasticsearch           │
│                       │                                          │
│                       └── Vector ─────▶ Pinecone / Milvus       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Comparison Table

| Database | Best For | Avoid When | Scale |
|----------|----------|------------|-------|
| **PostgreSQL** | OLTP, complex queries | Simple key-value | 10TB |
| **MySQL** | Read-heavy OLTP | Complex analytics | 10TB |
| **MongoDB** | Flexible schemas, documents | Many joins needed | 100TB |
| **Cassandra** | Write-heavy, time-series | Complex queries | Petabytes |
| **Redis** | Caching, sessions, pub/sub | Primary data store | 100GB |
| **Elasticsearch** | Full-text search, logs | Transactions | 100TB |
| **Neo4j** | Relationships, graphs | Tabular data | 1TB |
| **InfluxDB** | Metrics, IoT data | General purpose | 10TB |

---

## 8. API Design Principles

### REST API Best Practices

```
RESOURCE NAMING:
├── /users                  (collection)
├── /users/{id}             (specific resource)
├── /users/{id}/orders      (sub-resource)
└── /users/{id}/orders/{oid} (specific sub-resource)

HTTP METHODS:
├── GET     → Read (idempotent)
├── POST    → Create (not idempotent)
├── PUT     → Full update (idempotent)
├── PATCH   → Partial update (idempotent)
└── DELETE  → Remove (idempotent)

STATUS CODES:
├── 200 OK                  → Success with body
├── 201 Created             → Resource created
├── 204 No Content          → Success, no body
├── 400 Bad Request         → Client error (validation)
├── 401 Unauthorized        → Authentication required
├── 403 Forbidden           → Not permitted
├── 404 Not Found           → Resource doesn't exist
├── 409 Conflict            → State conflict
├── 422 Unprocessable       → Semantic error
├── 429 Too Many Requests   → Rate limited
├── 500 Internal Error      → Server error
└── 503 Service Unavailable → Temporarily down
```

### Request/Response Standards

```json
// Success Response
{
  "data": { ... },
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 100
  }
}

// Error Response
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Email is invalid",
    "details": [
      {
        "field": "email",
        "message": "Must be a valid email address"
      }
    ]
  }
}
```

### Versioning Strategy

```
RECOMMENDED: URL Path Versioning
├── /api/v1/users
├── /api/v2/users
└── Clear, explicit, cache-friendly

ALTERNATIVE: Header Versioning
├── Accept: application/vnd.api+json; version=1
└── Cleaner URLs, but harder to test

AVOID: Query Parameter
├── /api/users?version=1
└── Caching issues, easily forgotten
```

---

## 9. Security Architecture

### Defense in Depth

```
┌─────────────────────────────────────────────────────────────────┐
│                    SECURITY LAYERS                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  LAYER 1: PERIMETER                                             │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  • WAF (OWASP rules)                                    │   │
│  │  • DDoS protection                                       │   │
│  │  • Rate limiting                                         │   │
│  │  • Geo-blocking (if needed)                             │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  LAYER 2: NETWORK                                               │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  • VPC isolation                                        │   │
│  │  • Security groups (firewall)                           │   │
│  │  • Private subnets for databases                        │   │
│  │  • VPN for admin access                                 │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  LAYER 3: APPLICATION                                           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  • Input validation                                     │   │
│  │  • Output encoding                                      │   │
│  │  • Authentication (JWT, OAuth)                          │   │
│  │  • Authorization (RBAC/ABAC)                            │   │
│  │  • CSRF protection                                      │   │
│  │  • Secure headers (CSP, HSTS)                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  LAYER 4: DATA                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  • Encryption at rest (AES-256)                         │   │
│  │  • Encryption in transit (TLS 1.3)                      │   │
│  │  • Key management (KMS)                                 │   │
│  │  • Data masking for non-prod                            │   │
│  │  • PII handling procedures                              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Authentication Patterns

| Pattern | Use Case | Complexity |
|---------|----------|------------|
| **Session-based** | Traditional web apps | Low |
| **JWT** | Stateless APIs, microservices | Medium |
| **OAuth 2.0** | Third-party integration | High |
| **OIDC** | SSO, identity federation | High |
| **API Keys** | Server-to-server | Low |
| **mTLS** | Zero-trust, high security | High |

---

## 10. Observability Stack

### The Three Pillars

```
┌─────────────────────────────────────────────────────────────────┐
│                    OBSERVABILITY STACK                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐   │
│  │      LOGS       │ │     METRICS     │ │     TRACES      │   │
│  │                 │ │                 │ │                 │   │
│  │ • What happened │ │ • System health │ │ • Request flow  │   │
│  │ • Debugging     │ │ • Trends        │ │ • Latency       │   │
│  │ • Audit trail   │ │ • Alerting      │ │ • Dependencies  │   │
│  │                 │ │                 │ │                 │   │
│  │ Tools:          │ │ Tools:          │ │ Tools:          │   │
│  │ • ELK Stack     │ │ • Prometheus    │ │ • Jaeger        │   │
│  │ • Loki          │ │ • Grafana       │ │ • Zipkin        │   │
│  │ • Datadog       │ │ • Datadog       │ │ • Datadog       │   │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘   │
│                                                                  │
│  CORRELATION: All three linked by trace_id / request_id         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Essential Metrics (RED + USE)

```
RED Method (Request-oriented):
├── Rate      → Requests per second
├── Errors    → Failed requests per second
└── Duration  → Latency distribution (p50, p95, p99)

USE Method (Resource-oriented):
├── Utilization → % time resource is busy
├── Saturation  → Queue depth
└── Errors      → Error count

Golden Signals:
├── Latency     → How long requests take
├── Traffic     → How much demand
├── Errors      → How many failures
└── Saturation  → How "full" the service is
```

### Alerting Strategy

```
SEVERITY LEVELS:

P1 (Critical) - Page immediately
├── Service down
├── Data loss risk
├── Security breach
└── Response: <15 minutes

P2 (High) - Page during business hours
├── Degraded performance
├── High error rate
└── Response: <1 hour

P3 (Medium) - Ticket, next business day
├── Non-critical component issue
├── Warning thresholds
└── Response: <24 hours

P4 (Low) - Backlog
├── Cosmetic issues
├── Minor inefficiencies
└── Response: Sprint planning
```

---

## 11. Interview Presentation Template

### Opening (30 seconds)

> "For this system design, I'll structure my approach in four phases:
> 1. Clarify requirements and constraints
> 2. Design high-level architecture
> 3. Deep dive into critical components
> 4. Address scalability and trade-offs
>
> Let me start by understanding the requirements better..."

### Requirements Phase (3-5 minutes)

```
QUESTIONS TO ASK:

Functional:
• "What are the core features? What's the MVP?"
• "Who are the users? What are their main workflows?"
• "What integrations are needed?"

Scale:
• "How many users? Daily active? Peak concurrent?"
• "What's the expected data volume?"
• "Read-heavy or write-heavy?"

Non-Functional:
• "What's the latency requirement?"
• "What availability SLA do we need?"
• "Any compliance requirements?"

Constraints:
• "Budget constraints?"
• "Existing infrastructure we need to use?"
• "Team size and expertise?"
```

### Design Phase (10-15 minutes)

```
STRUCTURE YOUR EXPLANATION:

1. "Let me start with the high-level architecture..."
   [Draw main components and data flow]

2. "The key data models would be..."
   [Define core entities and relationships]

3. "For the API design, I'd use..."
   [Define main endpoints and contracts]

4. "The critical flow for [X] would work like this..."
   [Walk through a specific user journey]

5. "For storage, I'm choosing [X] because..."
   [Justify database choices]
```

### Deep Dive Phase (10-15 minutes)

```
PICK 2-3 AREAS TO GO DEEP:

Option A: Data Layer
• Schema design with indexes
• Sharding strategy
• Caching approach

Option B: Critical Algorithm
• Feed generation
• Matching algorithm
• Ranking logic

Option C: Reliability
• Failure modes
• Retry strategies
• Circuit breakers

Option D: Scalability
• Bottleneck analysis
• Horizontal scaling approach
• Capacity planning
```

### Trade-offs Discussion (5 minutes)

```
FRAME TRADE-OFFS CLEARLY:

"I chose [A] over [B] because:
• For our scale requirements, [A] provides [benefit]
• The downside is [drawback], but we mitigate by [solution]
• If requirements change to [scenario], we'd revisit this decision"

COMMON TRADE-OFFS:
• Consistency vs Availability (CAP)
• Latency vs Throughput
• Cost vs Performance
• Simplicity vs Flexibility
• Build vs Buy
```

### Closing (2 minutes)

> "To summarize the key design decisions:
> 1. [Decision 1] for [reason]
> 2. [Decision 2] for [reason]
> 3. [Decision 3] for [reason]
>
> The main trade-offs I made were [X] and [Y].
>
> If we had more time/resources, I'd add [future enhancements].
>
> Do you have any questions about specific components?"

---

## Quick Reference Card

### Before Every Design

```
□ Clarify functional requirements
□ Establish scale (users, data, requests)
□ Define latency requirements
□ Understand availability needs
□ Identify compliance constraints
□ Note existing infrastructure
```

### Every Architecture Needs

```
□ Load balancer
□ API gateway
□ Authentication service
□ Primary database
□ Caching layer
□ Message queue (if async)
□ Monitoring stack
□ Logging infrastructure
```

### Questions to Ask Yourself

```
□ Where are the single points of failure?
□ What happens if [component] fails?
□ How do we scale when traffic 10x?
□ Where is data stored and backed up?
□ How do we deploy updates safely?
□ How do we debug production issues?
□ What are the cost drivers?
```

---

*Last updated: February 3, 2026*
