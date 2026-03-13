"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

interface ModalProps {
  isOpen: boolean;
  children: React.ReactNode;
}

export default function Modal({ isOpen, children }: ModalProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    return () => setMounted(false);
  }, []);

  if (!isOpen || !mounted) return null;

  return createPortal(
    <div className="fixed top-0 left-0 right-0 bottom-0 backdrop-blur-lg z-[9999] flex items-center justify-center">
      {children}
    </div>,
    document.body,
  );
}
