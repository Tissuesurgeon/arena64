"use client";

import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

let registered = false;

export function registerGsap() {
  if (typeof window === "undefined" || registered) return;
  gsap.registerPlugin(ScrollTrigger);
  registered = true;
}

export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function kickoffTimeline(root: HTMLElement) {
  registerGsap();
  const reduced = prefersReducedMotion();
  const tl = gsap.timeline({ defaults: { ease: "power3.out" } });
  if (reduced) {
    gsap.set(root.querySelectorAll("[data-kickoff]"), { opacity: 1, y: 0 });
    return tl;
  }
  tl.from(root.querySelectorAll("[data-kickoff]"), {
    opacity: 0,
    y: 36,
    duration: 0.9,
    stagger: 0.12,
  });
  const lights = root.querySelectorAll("[data-floodlight]");
  if (lights.length) {
    gsap.to(lights, {
      opacity: 0.55,
      duration: 2.4,
      yoyo: true,
      repeat: -1,
      stagger: 0.4,
      ease: "sine.inOut",
    });
  }
  return tl;
}

export function scoreFlash(el: HTMLElement, points: number) {
  registerGsap();
  if (prefersReducedMotion()) return;
  gsap.fromTo(
    el,
    { scale: 0.7, opacity: 0 },
    { scale: 1.15, opacity: 1, duration: 0.25, yoyo: true, repeat: 1, ease: "back.out(2)" }
  );
  el.textContent = `+${points}`;
}

export function bracketReveal(items: NodeListOf<Element> | Element[]) {
  registerGsap();
  if (prefersReducedMotion()) return;
  gsap.from(items, { opacity: 0, x: -20, stagger: 0.08, duration: 0.5, ease: "power2.out" });
}

export function podiumLift(el: HTMLElement) {
  registerGsap();
  if (prefersReducedMotion()) return;
  gsap.from(el, { y: 80, opacity: 0, duration: 1, ease: "power3.out" });
}

export { gsap, ScrollTrigger };