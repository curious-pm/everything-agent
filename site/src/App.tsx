import { Header } from "./components/Header";
import { Hero } from "./components/Hero";
import { Timeline } from "./components/Timeline";
import { Exchanges } from "./components/Exchanges";
import { Privacy } from "./components/Privacy";
import { Install } from "./components/Install";
import { OpenSource } from "./components/OpenSource";
import { Footer } from "./components/Footer";

export function App() {
  return (
    <>
      <a className="skip" href="#main">Skip to content</a>
      <Header />
      <main id="main">
        <Hero />
        <Timeline />
        <Exchanges />
        <Privacy />
        <Install />
        <OpenSource />
      </main>
      <Footer />
    </>
  );
}
