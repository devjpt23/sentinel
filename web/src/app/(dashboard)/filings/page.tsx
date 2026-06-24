"use client";

import { useEffect } from "react";

export default function FilingsRedirect() {
  useEffect(() => {
    window.location.replace("/sec-filings");
  }, []);
  return null;
}
