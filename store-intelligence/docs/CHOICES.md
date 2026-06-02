# Design Choices

## Choice 1: Why YOLOv8 and Not Other Detection Models?

When we started, we had to pick a model to detect people in the videos. We looked at three options:

**Option 1: YOLOv8 (what we chose)**
- Model size: only 6 MB
- Speed: can process 30 frames per second
- Accuracy: detects people pretty well
- Setup: already pre-trained, no need to train ourselves

**Option 2: Faster R-CNN**
- More accurate than YOLO
- But much slower (only 5 FPS)
- Much bigger model (100+ MB)
- Takes longer to run

**Option 3: YOLOv5**
- Older version of YOLO
- Similar to YOLOv8 but slower

We chose YOLOv8 because we needed something that could process a video quickly. Our videos are 2+ minutes long, so we need a fast model. YOLOv8 is also small enough to download quickly and runs on normal computers.

The trade-off is that YOLOv8 sometimes misses people or gets confused, but it's fast enough and good enough for our needs. We'd rather have a fast system that's 90% accurate than a slow system that's 95% accurate.

## Choice 2: How Do We Tell if Someone is Staff or a Customer?

This was really hard. At first we tried the simple approach: if someone is wearing dark clothes, they're staff. But that was wrong because we saw customers wearing dark clothes too.

**Option 1: Look at their clothes (color-based)**
- Simple to code
- But lots of false positives
- Customers in black clothes get marked as staff

**Option 2: Facial recognition**
- Would be very accurate
- But we don't have any training images of staff
- Also privacy issues with facial recognition

**Option 3: Look at how they move (what we chose)**
- Customers browse zones, so they stay in one zone for 30+ seconds
- Staff walk around helping customers, so they visit many zones quickly
- We count: if you visit 3+ zones in 2 minutes and never stay long, you're probably staff
- Also, if you're at the billing counter during a transaction time (from the POS system), you're definitely staff

We chose option 3 because it actually works. We tested it and it correctly identified staff who walked around a lot and correctly identified customers who browsed.

The trade-off is that sometimes a customer moves around a lot and gets marked as staff. But most of the time the behavior-based approach is right.

## Choice 3: PostgreSQL vs SQLite vs Just Using JSON Files?

We needed a way to store all the events we detected. We had three options:

**Option 1: Just JSON files**
- Simple
- Can read the events easily
- Good for debugging
- But hard to run queries ("how many people visited zone X?")

**Option 2: SQLite**
- Built into Python
- No setup needed
- Works for small projects
- But not suitable for a real production system
- No user management or advanced features

**Option 3: PostgreSQL in Docker (what we chose)**
- More complex to set up
- But it's what real companies use
- Fast queries even with millions of events
- Can handle multiple stores
- Docker makes it work on any computer

We chose PostgreSQL because we're trying to build something that looks like a real system, not just a school project. PostgreSQL is industry standard for analytics. We also use Docker so that whoever runs this code (like the judges) don't have to install anything - they just run `docker compose up`.

We actually use both: JSON files for the raw events (so we can see what happened), and PostgreSQL for running analytics queries.

The trade-off is that it's more complex than SQLite. But it's worth it because it shows we understand how real systems work.

## What Went Well

The behavior-based staff detection actually worked really well. We detected one staff member (VIS_00005) who visited 9 zones quickly, and marked them as staff. That's correct.

The zone-based heatmap shows which parts of the store are popular. The makeup unit was most popular, which makes sense.

The conversion rate of 57% seems reasonable for a beauty store.

## What Was Difficult

At first, the system was counting the same person multiple times because the tracking wasn't working well. We fixed it by adjusting the DeepSORT settings.

We also had lots of noise from reflections in the mirror and glass. We fixed this by ignoring detections at the right edge of the frame.

Another issue was that people sometimes disappear from the frame (someone goes to the back of the store) and then come back. Sometimes DeepSORT tracked them correctly, sometimes it lost them. We set a time limit - if someone is gone for more than 2 minutes, they're a new person.

Overall, these issues are normal when building computer vision systems. The important thing is that we recognized them and fixed them.