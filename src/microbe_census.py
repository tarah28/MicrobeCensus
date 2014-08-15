#!/usr/bin/python

try:
    import sys
except Exception:
    print 'Module "sys" not installed'; exit()
   
try:
    import os
except Exception:
    print 'Module "os" not installed'; exit()
          
try:
    import optparse
except Exception:
    print 'Module "optparse" not installed'; exit()

try:
    from ags_functions import *
except Exception, e:
    print e
    print 'Could not import ags_functions'; exit()
    
#######################################################################################
#   FILEPATHS TO SRC AND DATA FILES
src_dir     = os.path.dirname(os.path.realpath(sys.argv[0]))
data_dir    = os.path.join(os.path.dirname(src_dir), 'data')
p_rapsearch = os.path.join(src_dir,  'rapsearch_2.15') 
p_db        = os.path.join(data_dir, 'rapdb_2.15')    
p_gene2fam  = os.path.join(data_dir, 'gene_fam.map')
p_gene2len  = os.path.join(data_dir, 'gene_len.map')
p_params    = os.path.join(data_dir, 'pars.map')
p_coeffs    = os.path.join(data_dir, 'coefficients.map')
p_weights   = os.path.join(data_dir, 'weights.map')
p_read_len  = os.path.join(data_dir, 'read_len.map')

#######################################################################################
#   OPTIONS, ARGUMENTS, HELP                                                          
parser = optparse.OptionParser(usage = "Usage: microbe_census [-options] <seqfile> <outfile>")
parser.add_option("-n", dest="nreads",       default=1e6,     help="number of reads to use for AGS estimation (default = 1e6)")
parser.add_option("-l", dest="read_length",  default=None,    help="trim reads to this length (default = median read length)")
parser.add_option("-f", dest="file_type",    default=None,    help="file type: fasta or fastq (default = autodetect)")
parser.add_option("-c", dest="qual_code",    default=None,    help="fastq quality score encoding: [sanger, solexa, illumina] (default: autodetect)")
parser.add_option("-t", dest="threads",      default=1,       help="number of threads to use for database search (default = 1)")
parser.add_option("-q", dest="min_quality",  default=-5,      help="minimum base-level PHRED quality score: default = -5; no filtering")
parser.add_option("-m", dest="mean_quality", default=-5,      help="minimum read-level PHRED quality score: default = -5; no filtering")
parser.add_option("-d", dest="filter_dups",  default=False,   help="filter duplicate reads (default: False)", action='store_true')
parser.add_option("-u", dest="max_unknown",  default=100,     help="max percent of unknown bases: default = 100%; no filtering")
parser.add_option("-k", dest="keep_tmp",     default=False,   help="keep temporary files (default: False)", action='store_true')

#   parse options
(options, args) = parser.parse_args()
try:
    p_reads = args[0]
    p_out = args[1]
    p_wkdir = os.path.dirname(p_out)
    nreads = options.nreads
    file_type = auto_detect_file_type(p_reads) if options.file_type is None else options.file_type
    read_length = auto_detect_read_length(p_reads, file_type, p_read_len) if options.read_length is None else options.read_length
    threads = options.threads
    max_depth = 1000000                
    min_quality = int(options.min_quality)
    mean_quality = float(options.mean_quality)
    qual_code = options.qual_code
    filter_dups = options.filter_dups
    max_unknown = float(options.max_unknown)/100
    keep_tmp = options.keep_tmp
except Exception, e:
    print "\nIncorrect number of command line arguments."
    print "\nUsage: microbe_census [-options] <seqfile> <outfile>"
    print "For all options enter: microbe_census -h\n"
    sys.exit()

#   check for valid values
read_lengths = read_list(p_read_len, header=True, dtype='int')
if read_length not in read_lengths:
    sys.exit("Invalid read length. Choose a supported read length:\n\t" + str(read_lengths))

if file_type == "fasta" and any([min_quality > -5, mean_quality > -5, qual_code is not None]):
    sys.exit("Quality filtering options are only available for FASTQ files")

if qual_code not in ['sanger', 'solexa', 'illumina', None]:
    sys.exit("Invalid FASTQ quality encoding. Choose from: " + str(['sanger', 'solexa', 'illumina']) + " or do not specify to autodetect")

if file_type not in ['fasta', 'fastq']:
    sys.exit("Invalid file type. Choose a supported file type: " + str(['fasta', 'fastq']))

if threads < 1:
    sys.exit("Invalid number of threads. Must be a positive integer.")

if nreads < 1:
    sys.exit("Invalid number of reads. Must be a positive integer.")

if not os.path.isfile(p_reads):
    sys.exit("Input file does not exist.")

#######################################################################################
#   MAIN

# 1. Downsample nreads of read_length from seqfile;
#       -optionally detect FASTQ format, remove duplicates, and perform quality filtering
if file_type == 'fastq':
    fastq_format = auto_detect_fastq_format(p_reads, max_depth) if qual_code is None else qual_code
    p_sampled_reads, read_ids = process_fastq(p_reads, p_wkdir, nreads, read_length, mean_quality, min_quality, filter_dups, max_unknown, fastq_format)
elif file_type == 'fasta':
    p_sampled_reads, read_ids = process_fasta(p_reads, p_wkdir, nreads, read_length, filter_dups, max_unknown)
n_reads_sampled = len(read_ids)

# 2. Search sampled reads against single-copy gene families using RAPsearch2
p_results, p_aln = search_seqs(p_sampled_reads, p_db, p_rapsearch, threads, keep_tmp, p_params)

# 3. Classify reads into gene families according to read length and family specific parameters
best_hits = classify_reads(p_results, p_aln, read_length, p_params, p_gene2fam, p_gene2len, keep_tmp, n_reads_sampled)

# 4. Count # of hits to each gene family
agg_hits = aggregate_hits(best_hits, read_length, p_params)

# 5. Predict average genome size:
#       -predict size using each of 30 gene models
#       -remove outlier predictions
#       -take a weighted average across remaining predictions
avg_size = pred_genome_size(agg_hits, n_reads_sampled, read_length, p_coeffs, p_weights)

# 6. Report results
write_results(p_out, n_reads_sampled, read_length, avg_size, keep_tmp, p_results, p_aln)
print 'Average genome size (bp):', avg_size



