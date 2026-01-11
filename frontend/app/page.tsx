import Link from "next/link";
import { getPosts } from "@/lib/posts";

export default function Home() {
  const posts = getPosts();

  return (
    <main className="flex min-h-screen flex-col items-center p-24 relative overflow-hidden">
      {/* Background Gradients */}
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden -z-10">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-blue-600/20 blur-[120px]" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-purple-600/20 blur-[120px]" />
      </div>

      <div className="relative flex place-items-center mb-16 z-[-1]">
        <h1 className="text-6xl font-bold tracking-tighter text-center">
          Affiliate <span className="text-gradient">Agents</span>
        </h1>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 max-w-6xl w-full">
        {posts.map((post) => (
          <Link href={`/posts/${post.slug}`} key={post.slug} className="group">
            <div className="h-full rounded-xl border border-white/10 bg-white/5 p-6 backdrop-blur-sm transition-all hover:bg-white/10 hover:border-white/20">
              <h2 className="mb-3 text-2xl font-semibold group-hover:text-blue-400 transition-colors">
                {post.title}
              </h2>
              <p className="text-sm text-gray-400 line-clamp-3">
                {post.excerpt}
              </p>
              <div className="mt-4 flex items-center text-sm text-blue-400 font-medium">
                Read Review <span className="ml-2 transition-transform group-hover:translate-x-1">-&gt;</span>
              </div>
            </div>
          </Link>
        ))}

        {posts.length === 0 && (
          <div className="col-span-full text-center text-gray-500">
            No posts generated yet. Run the agents!
          </div>
        )}
      </div>
    </main>
  );
}
