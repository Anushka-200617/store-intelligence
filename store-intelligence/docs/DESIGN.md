# Store Intelligence System Design

## What is this project?

We built a system that watches CCTV videos from a store and counts how many customers came in and how many actually bought something. It's basically a way to measure if the store is selling well.

## How does it work?

### Step 1: Find People in Videos

We use something called YOLOv8. It's a computer vision model that looks at each frame of the video and says "there's a person here, there's another person there". It's pretty fast and works well even with lots of people.

We process every 3rd frame to make it faster. We ignore detections that are too blurry or not confident enough.

### Step 2: Track the Same Person

Once we detect people, we need to follow them. If person A walks from one side of the store to another, we need to know it's the same person, not two different people.

We use DeepSORT for this. It remembers what people look like and matches them across frames. So if a customer leaves one zone and goes to another, we know it's the same customer.

### Step 3: Record What Happens

When people move around the store, we write down:
- When they enter the store
- What zones they go to (makeup section, skincare section, billing)
- How long they stay in each zone
- When they go to the billing counter
- When they leave

We save all this as events in a JSON file. Each event is one thing that happened, like "VIS_00001 entered SKINCARE_TOP zone".

### Step 4: Know Who is Staff and Who is Customer

The store has staff workers. We need to exclude them from our customer count, otherwise our numbers are wrong.

We figured out that staff move differently than customers:
- Customers stay in one zone for a long time, looking at products
- Staff walk around quickly from zone to zone, helping different customers

So we count how many zones a person visits and how long they stay. If they visit 5 zones in 2 minutes and never stay more than 3 seconds anywhere, they're probably staff.

For people at the billing counter, we check the store's sales records. If a transaction happened at that time, the person there is staff.

### Step 5: Calculate Results

We put all the events in a PostgreSQL database. Then we run queries to calculate:
- How many unique customers visited
- How many went to the billing area
- How many actually bought something (by matching with POS records)
- The conversion rate (customers who bought / total customers)
- Which zones are most popular
- How long people spend in each zone

## Results We Got

From the test store (Brigade Bangalore):
- We detected 14 unique customers
- 8 of them went to the billing area
- 8 of them bought something
- Conversion rate: 57.14%
- Most popular zone: Makeup unit (9 visits)
- Least popular zone: Skincare top (2 visits)

## Why We Built It This Way

We used YOLOv8 because it's small (only 6MB) and fast enough to process videos in real-time. We could have used more complicated models like Faster R-CNN, but they're slower.

We used DeepSORT to track people because it handles situations where someone disappears from the frame and comes back. Like if someone goes behind a shelf - DeepSORT remembers them and matches them when they reappear.

We used PostgreSQL to store events because it's fast, reliable, and we can run lots of queries on it. We also save the raw events as JSON files so we can debug things if needed.

We put everything in Docker containers because that way it works the same way on any computer. The judges can just run one command and everything starts working.

## What We Learned

The hardest part was figuring out staff vs customers. At first we just looked at what color clothes they wore. But that didn't work because customers also wear dark clothes. Looking at movement patterns works much better.

The second hardest part was dealing with people who partially leave the frame or get covered by something. DeepSORT handles most of this, but not all. Sometimes we detect the same person twice if they disappear for too long.

But overall the system works pretty well. We get a conversion rate of 57%, which seems reasonable for a beauty store.