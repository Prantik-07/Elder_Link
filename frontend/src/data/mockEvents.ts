import type { CareEvent } from "./types";

// Timestamps are relative to a fixed "now" so the demo reads sensibly no
// matter when it's actually run: "today" is always today, "yesterday" is
// always yesterday.
const now = new Date();
const today = (hours: number, minutes: number) => {
  const d = new Date(now);
  d.setHours(hours, minutes, 0, 0);
  return d.toISOString();
};
const yesterday = (hours: number, minutes: number) => {
  const d = new Date(now);
  d.setDate(d.getDate() - 1);
  d.setHours(hours, minutes, 0, 0);
  return d.toISOString();
};
const daysAgo = (days: number, hours: number, minutes: number) => {
  const d = new Date(now);
  d.setDate(d.getDate() - days);
  d.setHours(hours, minutes, 0, 0);
  return d.toISOString();
};

export const mockCareEvents: CareEvent[] = [
  {
    id: "evt-1",
    type: "medication",
    categoryLabel: "Possible medication miss",
    title: "I think Dad may have missed his morning medication.",
    summary: "Caregiver mentioned he might have skipped his morning dose.",
    whatHappened:
      "Caregiver reported that Dad may have missed his morning medication. They weren't completely sure.",
    occurredAt: today(6, 32),
    reportedBy: "Anita (Caregiver)",
    location: "At home",
    status: "needs_verification",
    verificationReason:
      "The caregiver used uncertain language (“I think”, “might have”), so this needs to be confirmed with Dad or another caregiver.",
    evidence: {
      transcript:
        "I think Dad missed his morning medicine. He might have forgotten... I'm not completely sure though.",
      segmentId: "seg-01",
      startTime: 0,
      endTime: 18,
      durationSeconds: 18,
    },
  },
  {
    id: "evt-2",
    type: "medication",
    title: "New blood-pressure medication started.",
    summary: "Doctor prescribed Amlodipine 5mg, once daily with breakfast.",
    whatHappened:
      "Priya confirmed the new prescription with the doctor's office and started Dad on the medication this morning.",
    occurredAt: today(8, 42),
    reportedBy: "Priya (Caregiver)",
    location: "At home",
    status: "verified",
    evidence: {
      transcript:
        "Dad's doctor started him on a new blood pressure medicine, Amlodipine, 5 milligrams once a day with breakfast. I already put it in his pill organizer for the week.",
      segmentId: "seg-02",
      startTime: 0,
      endTime: 22,
      durationSeconds: 22,
    },
  },
  {
    id: "evt-3",
    type: "observation",
    title: "Dad seemed more tired than usual.",
    summary: "Napped twice, less talkative than his usual mornings.",
    whatHappened:
      "Anita noticed Dad was unusually sleepy through the morning and napped twice before lunch, which is not typical for him.",
    occurredAt: today(7, 15),
    reportedBy: "Anita (Caregiver)",
    location: "At home",
    status: "verified",
    evidence: {
      transcript:
        "Dad seems a lot more tired than usual today. He's already napped twice this morning and wasn't very talkative at breakfast.",
      segmentId: "seg-03",
      startTime: 0,
      endTime: 15,
      durationSeconds: 15,
    },
  },
  {
    id: "evt-4",
    type: "concern",
    title: "Mild dizziness after morning walk.",
    summary: "Felt lightheaded for a minute, sat down and recovered.",
    whatHappened:
      "Ramesh reported Dad felt briefly dizzy after their usual walk. Dad sat down, rested for a few minutes, and said he felt fine afterward.",
    occurredAt: yesterday(17, 20),
    reportedBy: "Ramesh (Caregiver)",
    location: "Near the park",
    status: "uncertain",
    verificationReason:
      "It's unclear whether this was a one-off or related to the new blood pressure medication - worth watching for a pattern.",
    evidence: {
      transcript:
        "After our walk this evening Dad said he felt a little dizzy, just for a minute. He sat down on the bench and it passed. He seemed okay after that.",
      segmentId: "seg-04",
      startTime: 0,
      endTime: 20,
      durationSeconds: 20,
    },
  },
  {
    id: "evt-5",
    type: "routine",
    title: "Ate a good breakfast and was in good spirits.",
    summary: "Full plate, joked with Priya about the weekend.",
    whatHappened:
      "Priya reported a good, uneventful breakfast - Dad finished his full plate and was cheerful, chatting about weekend plans.",
    occurredAt: yesterday(8, 10),
    reportedBy: "Priya (Caregiver)",
    location: "At home",
    status: "verified",
    evidence: {
      transcript:
        "Good morning here - Dad ate his whole breakfast and was in a great mood, joking with me about going out this weekend.",
      segmentId: "seg-05",
      startTime: 0,
      endTime: 12,
      durationSeconds: 12,
    },
  },
  {
    id: "evt-6",
    type: "appointment",
    title: "Cardiology follow-up scheduled for next week.",
    summary: "Dr. Mehta's office confirmed Tuesday, 10:30 AM.",
    whatHappened:
      "Priya called to confirm the previously requested follow-up appointment with Dad's cardiologist.",
    occurredAt: daysAgo(2, 14, 5),
    reportedBy: "Priya (Caregiver)",
    location: "Phone call",
    status: "verified",
    evidence: {
      transcript:
        "Just confirmed with Dr. Mehta's office - Dad's cardiology follow-up is next Tuesday at 10:30 in the morning.",
      segmentId: "seg-06",
      startTime: 0,
      endTime: 14,
      durationSeconds: 14,
    },
  },
];
