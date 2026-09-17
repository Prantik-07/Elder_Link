import {
  Activity,
  Calendar,
  FileText,
  Heart,
  Pill,
  Eye,
  type LucideIcon,
} from "lucide-react";
import type { CareEventType } from "../data/types";

export interface CategoryMeta {
  label: string;
  icon: LucideIcon;
  iconColor: string;
  iconBg: string;
}

export const CATEGORY_META: Record<CareEventType, CategoryMeta> = {
  medication: {
    label: "Medication",
    icon: Pill,
    iconColor: "var(--color-med)",
    iconBg: "var(--color-med-soft)",
  },
  observation: {
    label: "Observation",
    icon: Eye,
    iconColor: "var(--color-obs)",
    iconBg: "var(--color-obs-soft)",
  },
  concern: {
    label: "Concern",
    icon: Heart,
    iconColor: "var(--color-concern)",
    iconBg: "var(--color-concern-soft)",
  },
  appointment: {
    label: "Appointment",
    icon: Calendar,
    iconColor: "var(--color-routine)",
    iconBg: "var(--color-routine-soft)",
  },
  vital: {
    label: "Vital",
    icon: Activity,
    iconColor: "var(--color-concern)",
    iconBg: "var(--color-concern-soft)",
  },
  routine: {
    label: "Routine",
    icon: FileText,
    iconColor: "var(--color-routine)",
    iconBg: "var(--color-routine-soft)",
  },
};

/**
 * "Possible medication miss" and similar events use a different tone
 * (amber, matching their needs_verification status) than a routine
 * medication update, even though both share type "medication".
 */
export function isFlaggedMiss(categoryLabel: string | undefined): boolean {
  return Boolean(categoryLabel && /miss|possible/i.test(categoryLabel));
}
