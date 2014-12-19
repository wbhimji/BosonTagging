from ROOT import *
import sys
import os
import copy
import numpy as n


ptweights = TH1F("ptreweight","ptreweight",100,0,3000);



nevents = {}

def NEvents(runNumber):
    global nevents
    if long(runNumber) in nevents.keys():
        return nevents[runNumber];
    else:
        return 1;

def loadEvents(filename):
    global nevents
    f = open(filename);
    for line in f:
        spl = line.strip().split(',')
        run = spl[0]
        ev = spl[1]
        nevents[long(run)] = float(ev)

    f.close()


def ptWeight(pt):
    global ptweights
    return ptweights.GetBinContent(ptweights.GetXaxis().FindBin(pt/1000));


def setupPtWeight(filename):
    global ptweights
    print 'ptfile: '+filename
    f = open(filename);
    numbins = 100
    step_size = 3000/numbins;
    counter = 1;
    running_bkg = 0
    running_sig = 0
    current_edge = 0
    next_edge = 0;
    next_edge = step_size;
    # normally 200 bins would be for 0 - 3500.  Now we are going
    # to say 3500/numbins instead.

    next_edge = current_edge+step_size;

    for line in f:
        spl = line.strip().split(',')
        print line
        edge = spl[0]
        bkg = spl[1]
        sig = spl[2]
      
        running_bkg += float(bkg);
        running_sig += float(sig);
      
        if (float(edge) >= next_edge):
            next_edge += step_size;
            if (running_sig == 0):
                ptweights.SetBinContent( counter, 0 );
            else:
                ptweights.SetBinContent( counter, running_bkg/running_sig );
            running_bkg = 0;
            running_sig = 0;
            counter+=1;
    tc = TCanvas()
    tc.cd()
    ptweights.Draw()
    tc.SaveAs('reweight.png')
    f.close();

def setupHistogram(fname, algorithm, treename, signal=False, ptfile = '',createptfile = False):
    '''
    Read in the jet mass from the input file and fill it into a histogram.  The histogram gets used to calculate the mass window.
    Keyword args:
    fname --- input file name.
    algorithm --- Algorithm being used.
    treename --- treename for input root file
    '''

    # load the NEvents file to weight by number of events
    eventsfile = fname.replace('root','nevents')
    loadEvents(eventsfile)


    # set up a struct so that the SetBranchAddress method can be used.
    # normally one would use tree.variable to access the variable, but since
    # this variable name changes for each algorithm this is a better way to do it.
    gROOT.ProcessLine("struct jet_t { Float_t mass; Float_t pt; Float_t eta;} ")
    # create an object of this struct
    jet = jet_t()
    if signal and not createptfile:
        setupPtWeight(ptfile)
    
    # open file and ttree
    f = TFile.Open(fname,"READ")
    tree = f.Get(treename)
    
    # set branch address for the groomed jet mass
    tree.SetBranchAddress("jet_"+algorithm+"_m", AddressOf(jet,'mass'))
    tree.SetBranchAddress("jet_CamKt12Truth_pt", AddressOf(jet,'pt'))
    tree.SetBranchAddress("jet_CamKt12Truth_eta", AddressOf(jet,'eta'))
    # histogram with 300 bins and 0 - 0.3 TeV range
    hist = TH1F("pt","pt",100,200*1000,3000*1000)    
    hist_rw = TH1F("ptrw","ptrw",100,200*1000,3000*1000)    
    pthist = TH1F("ptreweight","ptreweight",100,0,3000);
    # maximum number of entries in the tree
    entries = tree.GetEntries()
    
    # loop through
    for e in xrange(entries):
        tree.GetEntry(e)
        if e%1000 == 0:
            print 'Progress: ' + str(e) + '/' + str(entries)
        weight = 1*tree.mc_event_weight*tree.k_factor*tree.filter_eff*(1/NEvents(tree.mc_channel_number))
        weight2 = 1*tree.mc_event_weight*tree.k_factor*tree.filter_eff*(1/NEvents(tree.mc_channel_number))

        # fill the hist
        # check eta
        #if abs(jet.eta) <= 1.2:
        #    if jet.pt < 1000*1000 and jet.pt > 500*1000 and jet.mass < 200*1000 and jet.mass > 0:
        if jet.pt < 200*1000 and not createptfile:
            continue


        if signal and not createptfile:
            weight*=ptWeight(jet.pt)
        elif not signal:
            weight*=tree.xs
            weight2*=tree.xs
        hist.Fill(jet.pt,weight2)

        if createptfile:
            pthist.Fill(jet.pt/1000,weight)

        if weight <= 0 and False:
            print 'weight is 0!'
            print 'mc_event_weight: ' + str(tree.mc_event_weight)
            print 'k_factor: ' + str(tree.k_factor)
            print 'filter_eff: ' + str(tree.filter_eff)
            print 'xs: ' + str(tree.xs)
            print 'nevents: ' + str(NEvents(tree.mc_channel_number))
            print 'ptweight: ' + str(ptWeight(jet.pt))
        hist_rw.Fill(jet.pt,weight)

    
    return hist, hist_rw, pthist



def run(fname, algorithm, treename, ptfile):
    '''
    Method for running over a single algorithm and calculating the mass window.
    Keyword args:
    fname --- the input file name
    algorithm --- the name of the algorithm
    treename --- Name of tree in input root files
    ptfile --- pt reweighting file
    '''

    # setup the histogram - read in the mass entries from the input file and put them into a histogram
    createptfile = False
    if ptfile == '':
        createptfile = True
    hist_sig,hist_rw,pthist_sig = setupHistogram(fname, algorithm, treename, True, ptfile, createptfile)
    bkg_fname = fname.replace('sig','bkg')
    hist_bkg,tmp,pthist_bkg = setupHistogram(bkg_fname, algorithm, treename, False, '', createptfile)

    # folder where input file is
    folder = fname[:fname.rfind('/')+1]

    if createptfile:
        ptfile_out = open(folder+algorithm+'.ptweightsv2','w')
        for i in range(1,pthist_sig.GetXaxis().GetNbins()+1):
            sig = pthist_sig.GetBinContent(i)
            bkg = pthist_bkg.GetBinContent(i)
            edge = pthist_sig.GetXaxis().GetBinUpEdge(i)
            ptfile_out.write(str(edge)+','+str(bkg)+','+str(sig)+'\n')
        ptfile_out.close()

    # write this information out as a plot
    canv = TCanvas()
    canv.cd()
    canv.SetLogy()
    hist_sig.Scale(1/hist_sig.Integral())
    hist_bkg.Scale(1/hist_bkg.Integral())
    hist_rw.Scale(1/hist_rw.Integral())
    hist_sig.Draw()
    hist_bkg.SetLineColor(ROOT.kRed)
    hist_bkg.Draw("same")
    canv.SaveAs(folder+"pt_truth.png")
    hist_rw.Draw()
    hist_bkg.Draw("same")
    canv.SaveAs(folder+"pt_rw.png")

def runAll(input_file, file_id, treename):
    '''
    Method for running over a collection of algorithms and checking truth pt
    The algorithms are stored in a text file which is read in.  Each line gives the input folder, with the folder of the form ALGORITHM_fileID/.
    input_file --- the text file with the folders
    file_id --- the folder suffix
    treename --- Name of tree in input root files
    '''
    # open input file
    f = open(input_file,"read")
    # list that will store all of the filenames and corresponding algorithms
    fnames = []
    # read in file
    for l in f:
        # remove whitespace
        l = l.strip()+'/'
        # The input folder is given on each line
        folder = l
        # now get the files in this folder and iterate through, looking for the signal file
        fileslist = os.listdir(folder)
        sigfile = ""
        ptfile = ""
        for fil in fileslist:
            # found the signal file!
            if fil.endswith("sig.root"):
                sigfile = folder+fil
            if fil.endswith("ptweightsv2"):
                ptfile = folder+fil
        # the algorithm can be obtained from the folder by removing the leading
        # directory information and removing the file identifier
        alg = l.split('/')[-2][:-len(file_id)]
        # add these to the list to run over
        fnames.append([sigfile,alg])

    # loop through all of the algorithms and find the mass windows
    for a in fnames:
        print "running " + a[1]
        run(a[0],a[1],treename, ptfile)

if __name__=="__main__":
    print len(sys.argv)
    if len(sys.argv) < 3:
        print "usage: python calculateMassWindow.py text_file_with_folder_names folder_suffix(including leading underscore) [tree-name]"
        sys.exit()
    if len(sys.argv) == 3:
        runAll(sys.argv[1],sys.argv[2], 'physics')
    elif len(sys.argv) == 4:
        runAll(sys.argv[1],sys.argv[2],sys.argv[3])