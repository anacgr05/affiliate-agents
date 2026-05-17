"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

type AffiliateLink = {
  store: string;
  url: string;
  price: string;
};

type Product = {
  name: string;
  price: string;
  rating: number;
  pros: string[];
  cons: string[];
  verdict: string;
  affiliate_links: AffiliateLink[];
};

type BuyingStep = {
  title: string;
  content: string;
};

type FaqItem = {
  question: string;
  answer: string;
};

type Post = {
  slug: string;
  title: string;
  excerpt: string;
  image_url?: string | null;
  image_status?: string | null;
  hero?: {
    title: string;
    subtitle: string;
    image_prompt?: string;
    image?: string;
  };
  products: Product[];
  buying_guide?: {
    title?: string;
    steps: BuyingStep[];
  };
  faq?: FaqItem[];
};

function StarRating({ rating }: { rating: number }) {
  return (
    <div className="flex items-center gap-1">
      {[1, 2, 3, 4, 5].map((star) => (
        <svg
          key={star}
          className={`w-4 h-4 ${star <= Math.round(rating) ? "text-yellow-400" : "text-gray-200"}`}
          fill="currentColor"
          viewBox="0 0 20 20"
        >
          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
        </svg>
      ))}
      <span className="text-sm text-gray-500 ml-1">{rating.toFixed(1)}</span>
    </div>
  );
}

export default function ReviewPage() {
  const params = useParams();
  const slug = params.slug as string;

  const [post, setPost] = useState<Post | null>(null);
  const [coverUrl, setCoverUrl] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  useEffect(() => {
    fetch("/api/agent/posts")
      .then((r) => r.json())
      .then(({ posts }: { posts: Post[] }) => {
        const found = posts?.find((p) => p.slug === slug) ?? null;
        if (found) {
          setPost(found);
          if (found.image_url && found.image_status === "ready") {
            setCoverUrl(found.image_url);
          }
        } else {
          setNotFound(true);
        }
      })
      .catch(() => setNotFound(true));

    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
    const source = new EventSource(`${backendUrl}/agent/posts/stream?slug=${slug}`);
    source.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.type === "image_ready") {
        setCoverUrl(data.url);
        source.close();
      } else if (data.type === "image_failed") {
        source.close();
      }
    };
    return () => source.close();
  }, [slug]);

  if (notFound) {
    return <p className="p-8 text-gray-500">Post não encontrado.</p>;
  }

  if (!post) {
    return (
      <div className="max-w-4xl mx-auto p-6 animate-pulse space-y-4">
        <div className="h-64 bg-gray-200 rounded-xl" />
        <div className="h-8 bg-gray-200 rounded w-3/4" />
        <div className="h-4 bg-gray-200 rounded w-full" />
        <div className="h-4 bg-gray-200 rounded w-5/6" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-12">

      {/* ── Hero ─────────────────────────────────────────────── */}
      <section>
        <div className="w-full h-72 bg-gray-100 rounded-2xl overflow-hidden mb-6 relative">
          {coverUrl ? (
            <img src={coverUrl} alt={post.hero?.title ?? post.title} className="object-cover w-full h-full" />
          ) : (
            <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
              <p className="animate-pulse text-gray-400 text-sm">Gerando imagem com IA...</p>
            </div>
          )}
        </div>

        {post.hero?.title && (
          <h1 className="text-4xl font-bold text-gray-900 mb-3 leading-tight">
            {post.hero.title}
          </h1>
        )}
        {post.hero?.subtitle && (
          <p className="text-xl text-gray-500 mb-4">{post.hero.subtitle}</p>
        )}
        {(!post.hero?.title) && (
          <h1 className="text-4xl font-bold text-gray-900 mb-3">{post.title}</h1>
        )}
        <p className="text-gray-600 text-lg">{post.excerpt}</p>
      </section>

      {/* ── Produtos ─────────────────────────────────────────── */}
      {post.products?.length > 0 && (
        <section className="space-y-6">
          <h2 className="text-2xl font-bold text-gray-900 border-b border-gray-200 pb-3">
            Produtos em Destaque
          </h2>
          {post.products.map((product, i) => (
            <div key={i} className="border border-gray-200 rounded-xl p-6 hover:shadow-md transition-shadow">
              <div className="flex flex-wrap justify-between items-start gap-2 mb-3">
                <div>
                  <h3 className="text-xl font-bold text-gray-900">{product.name}</h3>
                  <StarRating rating={product.rating} />
                </div>
                <span className="text-2xl font-bold text-green-700">{product.price}</span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4 text-sm">
                <div className="bg-green-50 rounded-lg p-3">
                  <p className="font-semibold text-green-800 mb-2">Prós</p>
                  <ul className="space-y-1">
                    {product.pros.map((pro, j) => (
                      <li key={j} className="text-green-700 flex gap-2">
                        <span className="shrink-0">✓</span>{pro}
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="bg-red-50 rounded-lg p-3">
                  <p className="font-semibold text-red-800 mb-2">Contras</p>
                  <ul className="space-y-1">
                    {product.cons.map((con, j) => (
                      <li key={j} className="text-red-700 flex gap-2">
                        <span className="shrink-0">✗</span>{con}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              <p className="text-gray-600 text-sm italic mb-4 border-l-4 border-blue-200 pl-3">
                {product.verdict}
              </p>

              {product.affiliate_links?.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {product.affiliate_links.map((link, j) => (
                    <a
                      key={j}
                      href={link.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-2 bg-blue-600 text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
                    >
                      {link.store} — {link.price}
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                      </svg>
                    </a>
                  ))}
                </div>
              )}
            </div>
          ))}
        </section>
      )}

      {/* ── Guia de Compra ────────────────────────────────────── */}
      {(post.buying_guide?.steps?.length ?? 0) > 0 && (
        <section className="space-y-4">
          <h2 className="text-2xl font-bold text-gray-900 border-b border-gray-200 pb-3">
            {post.buying_guide?.title ?? "Guia de Compra"}
          </h2>
          <div className="space-y-4">
            {post.buying_guide?.steps.map((step, i) => (
              <div key={i} className="flex gap-4">
                <div className="shrink-0 w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center font-bold text-sm">
                  {i + 1}
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900 mb-1">{step.title}</h3>
                  <p className="text-gray-600 text-sm leading-relaxed">{step.content}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── FAQ ──────────────────────────────────────────────── */}
      {(post.faq?.length ?? 0) > 0 && (
        <section className="space-y-3">
          <h2 className="text-2xl font-bold text-gray-900 border-b border-gray-200 pb-3">
            Perguntas Frequentes
          </h2>
          {post.faq?.map((item, i) => (
            <div key={i} className="border border-gray-200 rounded-xl overflow-hidden">
              <button
                className="w-full text-left px-5 py-4 font-semibold text-gray-900 hover:bg-gray-50 flex justify-between items-center gap-4"
                onClick={() => setOpenFaq(openFaq === i ? null : i)}
              >
                <span>{item.question}</span>
                <svg
                  className={`w-5 h-5 text-gray-400 shrink-0 transition-transform ${openFaq === i ? "rotate-180" : ""}`}
                  fill="none" viewBox="0 0 24 24" stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {openFaq === i && (
                <div className="px-5 pb-4 text-gray-600 text-sm leading-relaxed border-t border-gray-100 pt-3">
                  {item.answer}
                </div>
              )}
            </div>
          ))}
        </section>
      )}

    </div>
  );
}
