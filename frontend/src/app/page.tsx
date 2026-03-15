"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { uploadDocument, uploadConfig, parseDocument } from "@/lib/api";
import { useSessionStore } from "@/lib/store";

export default function UploadPage() {
  const router = useRouter();
  const store = useSessionStore();
  const [docFile, setDocFile] = useState<File | null>(null);
  const [configFile, setConfigFile] = useState<File | null>(null);
  const [parsingHint, setParsingHint] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleDocDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file && (file.name.endsWith(".docx") || file.name.endsWith(".doc"))) {
      setDocFile(file);
    }
  }, []);

  const handleConfigDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file && (file.name.endsWith(".yaml") || file.name.endsWith(".yml"))) {
      setConfigFile(file);
    }
  }, []);

  const handleSubmit = async () => {
    if (!docFile) return;
    setLoading(true);
    setError("");

    try {
      const { session_id } = await uploadDocument(docFile);
      store.setSession(session_id);
      store.setDocumentUploaded(docFile.name);

      if (configFile) {
        await uploadConfig(session_id, configFile);
        store.setConfigUploaded(configFile.name);
      }

      const result = await parseDocument(session_id, parsingHint);
      store.setParsedData({
        documentTitle: result.document_title,
        sections: result.sections,
        config: result.config as any,
      });

      router.push(`/sessions/${session_id}/review`);
    } catch (e: any) {
      setError(e.message || "Upload failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center p-8">
      <div className="w-full max-w-2xl space-y-8">
        <div className="text-center space-y-2">
          <h1 className="text-3xl font-bold tracking-tight">QA Agent</h1>
          <p className="text-muted-foreground">
            Upload your test document and configuration to get started
          </p>
        </div>

        <Card
          className={`p-8 border-2 border-dashed cursor-pointer transition-colors ${
            docFile
              ? "border-green-500 bg-green-50 dark:bg-green-950"
              : "border-muted-foreground/25 hover:border-muted-foreground/50"
          }`}
          onDrop={handleDocDrop}
          onDragOver={(e) => e.preventDefault()}
          onClick={() => {
            const input = document.createElement("input");
            input.type = "file";
            input.accept = ".docx,.doc";
            input.onchange = (e) => {
              const file = (e.target as HTMLInputElement).files?.[0];
              if (file) setDocFile(file);
            };
            input.click();
          }}
        >
          <div className="text-center space-y-2">
            <p className="text-lg font-medium">
              {docFile ? `Selected: ${docFile.name}` : "Drop your test document here"}
            </p>
            <p className="text-sm text-muted-foreground">
              {docFile ? "Click to change" : "or click to browse — Accepts .docx, .doc"}
            </p>
          </div>
        </Card>

        <Card
          className={`p-8 border-2 border-dashed cursor-pointer transition-colors ${
            configFile
              ? "border-green-500 bg-green-50 dark:bg-green-950"
              : "border-muted-foreground/25 hover:border-muted-foreground/50"
          }`}
          onDrop={handleConfigDrop}
          onDragOver={(e) => e.preventDefault()}
          onClick={() => {
            const input = document.createElement("input");
            input.type = "file";
            input.accept = ".yaml,.yml";
            input.onchange = (e) => {
              const file = (e.target as HTMLInputElement).files?.[0];
              if (file) setConfigFile(file);
            };
            input.click();
          }}
        >
          <div className="text-center space-y-2">
            <p className="text-lg font-medium">
              {configFile
                ? `Selected: ${configFile.name}`
                : "Drop your configuration file here"}
            </p>
            <p className="text-sm text-muted-foreground">
              {configFile
                ? "Click to change"
                : "or click to browse — Accepts .yaml, .yml (optional)"}
            </p>
          </div>
        </Card>

        {/* Parsing Hint */}
        <div className="space-y-2">
          <label className="text-sm font-medium">
            Parsing Guidance (optional)
          </label>
          <Textarea
            placeholder="Help the AI find test cases in your document. Examples:&#10;- 'Test cases are in the tables starting from Section 3'&#10;- 'Each row in the table is a test case with columns: S.No, Test Name, Steps, Expected Result'&#10;- 'Ignore the first 2 pages, test cases start after the Requirements section'"
            value={parsingHint}
            onChange={(e) => setParsingHint(e.target.value)}
            rows={3}
            className="text-sm"
          />
          <p className="text-xs text-muted-foreground">
            The AI will read your entire document and extract test cases. Add hints if the document has an unusual format.
          </p>
        </div>

        {error && <p className="text-sm text-red-500 text-center">{error}</p>}

        <div className="flex justify-center">
          <Button size="lg" onClick={handleSubmit} disabled={!docFile || loading}>
            {loading ? "Parsing with AI..." : "Parse & Continue"}
          </Button>
        </div>
      </div>
    </div>
  );
}
