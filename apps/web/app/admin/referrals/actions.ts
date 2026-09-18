"use server";

import { revalidatePath } from "next/cache";
import { operatorApi } from "@/lib/auth/operator";

function dollarsToCents(value: FormDataEntryValue | null) {
  const amount = Number(String(value ?? "0").trim() || "0");
  if (!Number.isFinite(amount) || amount < 0) return 0;
  return Math.round(amount * 100);
}

export async function qualifyReferral(formData: FormData) {
  const eventId = String(formData.get("event_id") ?? "");
  if (!eventId) return;
  await operatorApi(`referrals/${eventId}/qualify`, {
    method: "POST",
    body: JSON.stringify({
      referrer_credit_cents: dollarsToCents(formData.get("referrer_credit_usd")),
      referred_credit_cents: dollarsToCents(formData.get("referred_credit_usd")),
    }),
  });
  revalidatePath("/admin/referrals");
}
