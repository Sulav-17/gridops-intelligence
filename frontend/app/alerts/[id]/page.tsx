import { AlertDetailPage } from "@/components/decision-support";
export default async function Page({ params }: { params: Promise<{ id: string }> }) { const { id } = await params; return <AlertDetailPage alertId={Number(id)} />; }
