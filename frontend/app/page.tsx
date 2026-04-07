import DashboardPage from "@/components/dashboard-page";

export default function HomePage() {
  return (
    <DashboardPage
      channels={["redlinkleb"]}
      mode="redalerts"
      titleAr="الخروقات الجوية"
      titleEn="Air Violations"
      subtitleAr="Air Violations"
      subtitleEn="الخروقات الجوية"
    />
  );
}
