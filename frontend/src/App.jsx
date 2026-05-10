import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Header from './components/Header';
import Dashboard from './pages/Dashboard';
import ReportPage from './pages/ReportPage';
import HistoryPage from './pages/HistoryPage';
import CollectionsPage from './pages/CollectionsPage';
import HubPage from './pages/HubPage';

export default function App() {
  return (
    <BrowserRouter>
      <Header />
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/report/:id" element={<ReportPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/collections" element={<CollectionsPage />} />
        <Route path="/hub" element={<HubPage />} />
      </Routes>
    </BrowserRouter>
  );
}
