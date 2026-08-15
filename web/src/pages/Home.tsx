import NavBar from '@/components/marketing/NavBar'
import Hero from '@/components/marketing/Hero'
import FeatureGrid from '@/components/marketing/FeatureGrid'
import Footer from '@/components/marketing/Footer'

// Public landing page -- visible only to logged-out visitors (RootGate in
// App.tsx). No Shell chrome: a logged-out visitor must never see
// authenticated nav.
export default function Home() {
  return (
    <div className="min-h-screen bg-background font-sans">
      <NavBar />
      <Hero />
      <FeatureGrid />
      <Footer />
    </div>
  )
}
