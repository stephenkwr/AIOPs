"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, UploadCloud } from "lucide-react";
import { useRef, useState } from "react";

import { uploadDocument } from "@/lib/api/documents";
import { cn } from "@/lib/utils";

const ACCEPT = ".pdf,.html,.htm,.csv,.txt,.md";

export function UploadDropzone() {
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: uploadDocument,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
    onError: (err: Error) => setErrorMsg(err.message),
  });

  function handleFiles(files: FileList | null) {
    setErrorMsg(null);
    if (!files) return;
    for (const file of Array.from(files)) {
      mutation.mutate(file);
    }
  }

  return (
    <div>
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          handleFiles(e.dataTransfer.files);
        }}
        className={cn(
          "flex w-full flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors",
          dragOver
            ? "border-slate-900 bg-slate-100"
            : "border-slate-300 bg-white hover:border-slate-400 hover:bg-slate-50",
        )}
      >
        {mutation.isPending ? (
          <Loader2 className="h-6 w-6 animate-spin text-slate-500" />
        ) : (
          <UploadCloud className="h-6 w-6 text-slate-500" />
        )}
        <div className="text-sm font-medium text-slate-700">
          {mutation.isPending ? "Uploading…" : "Drop files here, or click to browse"}
        </div>
        <div className="text-xs text-slate-500">PDF, HTML, CSV, TXT, or Markdown · up to 10 MB</div>
      </button>

      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ACCEPT}
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />

      {errorMsg && <p className="mt-2 text-sm text-red-600">{errorMsg}</p>}
    </div>
  );
}
