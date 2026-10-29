import { useEffect, type RefObject } from "react";

const owners = new Set<symbol>();
let restorePage: (() => void) | undefined;

/** A nested dialog cannot release another dialog's scroll lock. */
export function lockPageScroll() {
  const owner = Symbol("dialog");
  if (!owners.size) {
    const { body, documentElement: html } = document;
    const x = window.scrollX,
      y = window.scrollY;
    const properties = [
      "position",
      "top",
      "left",
      "width",
      "overflow",
      "padding-right",
    ];
    const saved = properties.map((name) => [
      name,
      body.style.getPropertyValue(name),
      body.style.getPropertyPriority(name),
    ]);
    const overflow = html.style.overflow;
    const behavior = html.style.scrollBehavior;
    const gap = Math.max(0, window.innerWidth - html.clientWidth);
    const padding = parseFloat(getComputedStyle(body).paddingRight) || 0;
    Object.assign(body.style, {
      position: "fixed",
      top: `${-y}px`,
      left: `${-x}px`,
      width: "100%",
      overflow: "hidden",
    });
    if (gap) body.style.paddingRight = `${padding + gap}px`;
    html.style.overflow = "hidden";
    restorePage = () => {
      for (const [name, value, priority] of saved) {
        if (value) body.style.setProperty(name, value, priority);
        else body.style.removeProperty(name);
      }
      html.style.overflow = overflow;
      html.style.scrollBehavior = "auto";
      window.scrollTo({ left: x, top: y, behavior: "instant" });
      html.style.scrollBehavior = behavior;
    };
  }
  owners.add(owner);
  return () => {
    if (!owners.delete(owner)) return;
    if (!owners.size) {
      restorePage?.();
      restorePage = undefined;
    }
  };
}

export function useDialogLifecycle(
  ref: RefObject<HTMLDialogElement | null>,
  focusInput = false,
) {
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const previous =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    const release = lockPageScroll();
    const resize = () =>
      node.style.setProperty(
        "--dialog-viewport-height",
        `${window.visualViewport?.height || window.innerHeight}px`,
      );
    resize();
    window.visualViewport?.addEventListener("resize", resize);
    try {
      node.showModal();
      const target = focusInput
        ? node.querySelector<HTMLElement>(
            'input:not([type="hidden"]), select, textarea',
          )
        : node;
      target?.focus({ preventScroll: true });
    } catch (error) {
      window.visualViewport?.removeEventListener("resize", resize);
      release();
      throw error;
    }
    return () => {
      node.close();
      window.visualViewport?.removeEventListener("resize", resize);
      release();
      if (previous?.isConnected) previous.focus({ preventScroll: true });
    };
  }, [ref, focusInput]);
}
