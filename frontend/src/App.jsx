import JobList from "./pages/JobList";

function App() {
  return (
    <div className="min-h-screen bg-gray-100">
      <header className="bg-white shadow-sm">
        <div className="max-w-5xl mx-auto px-4 py-4">
          <h1 className="text-2xl font-bold text-gray-900">Job App Helper</h1>
        </div>
      </header>
      <main className="max-w-5xl mx-auto px-4 py-8">
        <JobList />
      </main>
    </div>
  );
}

export default App;
